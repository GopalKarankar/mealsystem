# NVIDIA Parakeet STT Swap — Dev Prompt

**Purpose**: You are replacing the Groq Whisper transcription step with NVIDIA's Parakeet ASR model (hosted gRPC API) in this FastAPI/MongoDB meal-ingestion codebase. This prompt describes the current Groq wiring, the target NVIDIA Parakeet integration, required config changes, invariants to preserve, and known pitfalls.

---

## Context: Before and After

**Current** (`backend/app/services/whisper_service.py`):
- Calls `groq.Groq(api_key=settings.groq_api_key).audio.transcriptions.create(model=settings.whisper_model, file=(...), ...)` 
- Model: `"whisper-large-v3"` (default), hosted by Groq, REST endpoint
- Accepts `.wav`, `.mp3`, `.m4a`, `.webm` files
- Raises `ValueError` on failure (caught by route handler `meals.py:62-64` → HTTP 422)

**Target** (NVIDIA Parakeet, hosted gRPC API):
- Call `riva.client.ASRService(auth).offline_recognize(audio_bytes, config)` over gRPC
- Model: `parakeet-tdt-0.6b-v2` (English-only) or `-v3` (multilingual), hosted at `grpc.nvcf.nvidia.com:443`
- Requires audio format conversions: only WAV/OGG/OPUS supported (not `.mp3`/`.m4a`/`.webm`)
- Requires explicit language code (`en-US` default), unlike Whisper's auto-detect
- Raises `ValueError` on failure (downstream unchanged)
- Reuses `settings.nvidia_api_key` (adds new fields for gRPC config)

**Invariant**: The function signature `transcribe(audio_file_path: str) -> str` and error contract (raise `ValueError`) remain unchanged. All downstream code (Mongo doc, LLM parse, Qdrant embedding) sees an identical transcript string.

---

## Current Architecture (Groq Whisper)

**File**: `backend/app/services/whisper_service.py` (40 lines)

```python
import logging
import os
from groq import Groq
from app.config import settings

logger = logging.getLogger(__name__)

_EXTENSION_MIME_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".webm": "audio/webm",
}

def transcribe(audio_file_path: str) -> str:
    """Transcribe audio file using Groq Whisper API."""
    client = Groq(api_key=settings.groq_api_key)

    try:
        ext = os.path.splitext(audio_file_path)[1].lower()
        mime_type = _EXTENSION_MIME_TYPES.get(ext, "audio/wav")

        with open(audio_file_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model=settings.whisper_model,                # "whisper-large-v3"
                file=(audio_file_path.split("/")[-1], audio_file, mime_type),
            )
        transcript = response.text.strip()

        if not transcript:
            raise ValueError("Transcription produced empty text")

        return transcript

    except ValueError as e:
        if "API key" in str(e):
            raise ValueError("Whisper authentication failed - check GROQ_API_KEY")
        raise
    except Exception as e:
        error_str = str(e)
        if "timeout" in error_str.lower():
            raise ValueError("Transcription timed out (exceeded 30 seconds)")
        elif "audio" in error_str.lower() or "format" in error_str.lower():
            raise ValueError(f"Unsupported or corrupt audio format: {error_str}")
        else:
            raise ValueError(f"Transcription failed: {error_str}")
```

**Call site** (`backend/app/services/meal_service.py:82`):
```python
def create_meal_from_audio(user_id, audio_path: str, db) -> dict:
    try:
        transcript = whisper_service.transcribe(audio_path)    # GROQ CALL HERE
        raw_items = llm_service.parse_meal(transcript)         # Next: LLM parse
        # ... validation, Mongo insert, Qdrant index ...
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)                              # Always clean up
```

**Downstream usage**:
- Line 111–112: stored as `"original_text"` and `"transcription_text"` (both identical, raw transcript)
- Line 83: passed to `llm_service.parse_meal(transcript)` for LLM-based parsing
- Line 141: re-passed to `embedding_service.embed_text(transcript, input_type="passage")` for Qdrant indexing

---

## Target Architecture (NVIDIA Parakeet, Hosted gRPC)

### Dependency

Add `nvidia-riva-client` to `backend/requirements.txt`:
```
nvidia-riva-client==2.17.0  # (or latest compatible version)
```

This pulls `grpcio`, `protobuf`, and Riva protocol buffers.

### New Configuration Fields

Add to `backend/app/config.py` (within the `Settings` class):
```python
nvidia_asr_function_id: str          # Per-model function-id from build.nvidia.com
nvidia_asr_grpc_uri: str = "grpc.nvcf.nvidia.com:443"
nvidia_asr_language_code: str = "en-US"  # Parakeet requires explicit language code
```

Add to `backend/.env.example`:
```
NVIDIA_ASR_FUNCTION_ID=             # Copy from build.nvidia.com/nvidia/parakeet-tdt-0_6b-v2/api
NVIDIA_ASR_GRPC_URI=grpc.nvcf.nvidia.com:443
NVIDIA_ASR_LANGUAGE_CODE=en-US
```

**Critical**: `NVIDIA_API_KEY` (already configured for embeddings) must also have Parakeet ASR enabled in your build.nvidia.com account — Parakeet is a separate product surface from the embedding NIM, not a single unified key.

### New `transcribe()` Implementation (Sketch)

```python
import logging
from riva.client import Auth, ASRService
from riva.client.proto import riva_asr_pb2
from app.config import settings

logger = logging.getLogger(__name__)

def transcribe(audio_file_path: str) -> str:
    """Transcribe audio file using NVIDIA Parakeet ASR (hosted gRPC API)."""
    
    # Read audio file as raw bytes (Riva gRPC expects raw audio, not multipart)
    with open(audio_file_path, "rb") as f:
        audio_bytes = f.read()
    
    try:
        # Create gRPC auth with metadata headers
        auth = Auth(
            uri=settings.nvidia_asr_grpc_uri,           # "grpc.nvcf.nvidia.com:443"
            use_ssl=True,
            metadata_args=[
                ["function-id", settings.nvidia_asr_function_id],
                ["authorization", f"Bearer {settings.nvidia_api_key}"]
            ]
        )
        
        # Connect to Parakeet ASR service
        asr_service = ASRService(auth)
        
        # Build transcription config
        config = riva_asr_pb2.RecognitionConfig(
            encoding=riva_asr_pb2.LINEAR_PCM,      # WAV/PCM 16-bit mono expected
            sample_rate_hertz=16000,
            language_code=settings.nvidia_asr_language_code,  # "en-US"
            max_alternatives=1,
        )
        
        # Perform offline (file-based) transcription
        response = asr_service.offline_recognize(
            audio=audio_bytes,
            config=config,
            deadline=30.0  # 30-second gRPC deadline
        )
        
        # Extract transcript from response
        if response.results and response.results[0].alternatives:
            transcript = response.results[0].alternatives[0].transcript.strip()
        else:
            transcript = ""
        
        if not transcript:
            raise ValueError("Parakeet transcription produced empty text")
        
        return transcript
    
    except ValueError:
        raise  # Re-raise ValueError as-is (expected by route handler)
    except Exception as e:
        error_str = str(e)
        if "deadline" in error_str.lower():
            raise ValueError("Transcription timed out (exceeded 30 seconds)")
        elif "authentication" in error_str.lower() or "unauthorized" in error_str.lower():
            raise ValueError("Parakeet authentication failed - check NVIDIA_API_KEY and NVIDIA_ASR_FUNCTION_ID")
        else:
            raise ValueError(f"Transcription failed: {error_str}")
```

**Key differences from Groq**:
- gRPC client instantiated fresh per call (mirrors current pattern)
- Audio passed as raw bytes, not multipart file handle
- Requires explicit `RecognitionConfig` protobuf (language code, sample rate, encoding)
- Response shape is `riva_asr_pb2.StreamingRecognizeResponse` with `.results[0].alternatives[0].transcript` path
- gRPC deadline (30s) must be set explicitly on the call

### Audio Format Handling — **Major Change**

**Current**: Groq Whisper accepts `.wav`, `.mp3`, `.m4a`, `.webm` directly. Encoder auto-detection.

**Target**: Parakeet's hosted gRPC API only accepts **WAV/OGG/OPUS** (16-bit mono, 16 kHz sample rate). MP3/M4A/WebM uploads will fail.

**Design choice to make**:
1. **Transcode on backend** (recommended): Add `ffmpeg`-based transcoding to `whisper_service.py`. Dependency: `pydub` or shell-out to `ffmpeg` binary. Converts `.mp3`/`.m4a`/`.webm` → `.wav` before sending to Parakeet.
   - Pros: Transparent to frontend, handles legacy formats
   - Cons: adds infrastructure (ffmpeg or pydub), CPU cost, new failure modes
2. **Reject non-WAV formats**: Update route validation (`backend/app/routes/meals.py:30`) and `ALLOWED_AUDIO_EXTENSIONS` to only `.wav`. Require frontend to enforce WAV upload.
   - Pros: Simpler, no new dependencies
   - Cons: breaking change for users with MP3/M4A workflows

**Placeholder**: This doc assumes option 1 (transcode). Update the implementation section if option 2 is chosen.

---

## Configuration Fields

| Field | Env Var | Default | Notes |
|-------|---------|---------|-------|
| `nvidia_api_key` | `NVIDIA_API_KEY` | (none) | Required; reused from embeddings. Must have Parakeet ASR access enabled. |
| `nvidia_asr_function_id` | `NVIDIA_ASR_FUNCTION_ID` | (none) | **Per-model & account-specific**; copy from build.nvidia.com for your chosen Parakeet variant. |
| `nvidia_asr_grpc_uri` | `NVIDIA_ASR_GRPC_URI` | `grpc.nvcf.nvidia.com:443` | Hosted gRPC endpoint (same for all models). |
| `nvidia_asr_language_code` | `NVIDIA_ASR_LANGUAGE_CODE` | `en-US` | Required by Parakeet; set per deployment or make configurable per request. |

**Groq fields** (superseded but not removed):
- `groq_api_key` — still used by `llm_service.py` for Llama parsing; keep in config
- `whisper_model` — **no longer used**; can be removed from config and `.env.example`

**Dependencies in `requirements.txt`**:
```
groq==0.11.0        # Still used for Llama LLM parsing; keep
nvidia-riva-client==2.17.0  # NEW: Parakeet gRPC client
openai==1.54.0      # Still used for embedding service; keep
```

---

## Rules You Must Preserve

1. **Signature & Error Contract**: `transcribe(audio_file_path: str) -> str` and raise `ValueError` on any error. Do not change the function name, parameter types, or exception type. The route handler (`meals.py:62-64`) specifically catches `ValueError` → HTTP 422; any other exception becomes HTTP 500.

2. **Temp File Cleanup**: The `try/finally` in `meal_service.create_meal_from_audio` deletes the temp audio file after transcription succeeds or fails:
   ```python
   finally:
       if os.path.exists(audio_path):
           os.remove(audio_path)
   ```
   Do not modify this cleanup. Parakeet service must read the file and close it before this `finally` block runs.

3. **Downstream Invariance**: The transcript string flows unchanged to:
   - `llm_service.parse_meal(transcript)` — LLM parse step (line 83)
   - Mongo document fields `"original_text"` and `"transcription_text"` (lines 111–112)
   - `embedding_service.embed_text(transcript, input_type="passage")` for Qdrant (line 141)

   The swap only changes *how* the transcript is produced, not *what* it contains. Do not strip, normalize, or filter the transcript text.

4. **Test Mocking Pattern**: Existing tests in `backend/tests/test_meal_service.py` mock `app.services.meal_service.whisper_service.transcribe` with `@patch(...)`. This pattern must continue to work. Keep the function at `backend/app/services/whisper_service.transcribe()` (module path and function name) or update all 4 test decorators if renaming.

---

## Known Pitfalls

- **Audio format mismatch (biggest risk)**: Parakeet only accepts WAV/OGG/OPUS; Groq accepted MP3/M4A/WebM. If transcoding is not added, any `.mp3`/`.m4a`/`.webm` upload will fail at Parakeet with a gRPC error. Flag this early in PRs and testing. If using option 2 (reject non-WAV), document the breaking change in release notes.

- **Function-ID is per-model & account-specific**: The `function-id` metadata header uniquely identifies *which* Parakeet model variant and *which* NVIDIA account's API instance to use. Copying the wrong ID silently routes to the wrong model (e.g., v2 English-only vs v3 multilingual). Verify the ID from build.nvidia.com and test end-to-end.

- **gRPC vs REST protocol**: This is the first gRPC integration in this codebase (embedding and LLM services use REST SDKs). gRPC has different error semantics, timeout handling, and connection pooling than REST. Do not assume REST debugging tactics apply. Check [NVIDIA NIM Riva ASR docs](https://docs.nvidia.com/nim/riva/asr/latest/getting-started.html) for gRPC-specific troubleshooting.

- **Deadline vs no deadline**: Current `whisper_service.py` has no explicit timeout (the "30 seconds" is just a string). The gRPC `offline_recognize` call **must** have an explicit `deadline=` argument (e.g., `30.0` seconds) or network hangs will block indefinitely. Set a deadline.

- **Sample rate & encoding mismatch**: Parakeet expects 16-bit mono PCM at 16 kHz. If transcoding is implemented, ensure the output meets this spec, else Parakeet will reject the audio. If no transcoding, validate input files meet the spec before sending.

- **No multi-language auto-detect**: Unlike Whisper, Parakeet requires an explicit `language_code` setting. The v3 model supports auto-detect via `language_code="multi"`, but v2 (English-only) does not. Document this constraint.

- **SPEC.md dangling reference**: `README.md` and `CLAUDE.md` cross-reference a `SPEC.md` file (e.g., "See SPEC.md § 8") that does not exist in the repo. Not caused by this swap, but document it if you update those files.

---

## Quick Reference: Config Path

When implementing, update these files in this order:

1. **`backend/requirements.txt`**: Add `nvidia-riva-client==2.17.0`
2. **`backend/app/config.py`**: Add `nvidia_asr_function_id`, `nvidia_asr_grpc_uri`, `nvidia_asr_language_code` fields
3. **`backend/.env.example`**: Add `NVIDIA_ASR_FUNCTION_ID=`, `NVIDIA_ASR_GRPC_URI=...`, `NVIDIA_ASR_LANGUAGE_CODE=...`
4. **`.env` (dev)**: Set `NVIDIA_ASR_FUNCTION_ID` from your build.nvidia.com account
5. **`backend/app/services/whisper_service.py`**: Replace Groq client + call with Riva gRPC client + call (preserve function signature & error contract)
6. **`backend/app/services/meal_service.py`** (optional): Handle audio format transcoding if needed (new dependency)
7. **`backend/app/routes/meals.py`** (optional): Update `ALLOWED_AUDIO_EXTENSIONS` if restricting to WAV-only
8. **`backend/.env.example`** (optional): Document any new audio format restrictions or transcoding behavior

---

## Testing Checklist

- [ ] NVIDIA API key has Parakeet ASR enabled on build.nvidia.com (check account permissions)
- [ ] Correct `function-id` copied from build.nvidia.com for chosen model variant (v2 or v3)
- [ ] `nvidia-riva-client` installed: `pip list | grep nvidia-riva-client`
- [ ] `NVIDIA_ASR_FUNCTION_ID`, `NVIDIA_ASR_GRPC_URI`, `NVIDIA_ASR_LANGUAGE_CODE` set in local `.env`
- [ ] Sample WAV file transcribes end-to-end: `curl -X POST http://localhost:8000/meals/voice -F file=@sample.wav` (with auth header)
- [ ] Transcript appears correctly in Mongo document (`original_text`, `transcription_text` fields)
- [ ] Transcript is passed to LLM parse step (check logs for meal item output)
- [ ] Transcript is embedded in Qdrant (check Qdrant collection for new vector points)
- [ ] Non-WAV upload (MP3/M4A/WebM) either transcodes successfully or returns clear HTTP 422 error
- [ ] All 4 existing mocked tests in `backend/tests/test_meal_service.py` still pass without modification
- [ ] Error path (invalid API key, network timeout, empty audio) raises HTTP 422 (not 500)
- [ ] Temp audio file is cleaned up after both success and failure (no `/tmp` bloat)

---

## Sources & References

- [NVIDIA Parakeet TDT on build.nvidia.com](https://build.nvidia.com/nvidia/parakeet-tdt-0_6b-v2/api)
- [NVIDIA NIM Riva ASR Documentation](https://docs.nvidia.com/nim/riva/asr/latest/getting-started.html)
- [nvidia-riva-client PyPI](https://pypi.org/project/nvidia-riva-client/)
- Current codebase: `backend/app/services/whisper_service.py`, `meal_service.py`, `embedding_service.py` (pattern reference)
- Existing dev-prompt docs: `docs/qdrant-embeddings-prompt.md`, `docs/remove-usda-dependency-prompt.md` (format reference)
