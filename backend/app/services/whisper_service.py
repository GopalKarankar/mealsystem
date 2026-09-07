import logging
import os
import shutil
import tempfile
import wave
from riva.client import Auth, ASRService, AudioEncoding
from riva.client.proto import riva_asr_pb2
from pydub import AudioSegment
from app.config import settings

logger = logging.getLogger(__name__)


def transcribe(audio_file_path: str) -> str:
    """Transcribe audio file using NVIDIA Parakeet ASR (hosted gRPC API).

    Args:
        audio_file_path: Path to audio file (.wav, .mp3, .m4a, .webm)

    Returns:
        Transcript text

    Raises:
        ValueError: If API key invalid, audio format unsupported, timeout, etc.
    """
    wav_path = audio_file_path
    try:
        ext = os.path.splitext(audio_file_path)[1].lower()

        if settings.debug:
            file_size = os.path.getsize(audio_file_path)
            logger.info(f"[DIAG] Input: {audio_file_path}, ext={ext}, size={file_size} bytes")

        if ext != ".wav":
            wav_path = _transcode_to_wav(audio_file_path)
            if settings.debug and os.path.exists(wav_path):
                wav_size = os.path.getsize(wav_path)
                logger.info(f"[DIAG] Transcoded WAV: size={wav_size} bytes")

        with wave.open(wav_path, "rb") as wf:
            n_frames = wf.getnframes()
            frame_rate = wf.getframerate()
            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            audio_bytes = wf.readframes(n_frames)
            duration_sec = n_frames / frame_rate if frame_rate else 0

        if settings.debug:
            logger.info(f"[DIAG] WAV frames: {n_frames}, rate={frame_rate}, channels={n_channels}, sample_width={sample_width} bytes, duration={duration_sec:.3f}s")
            if duration_sec < 0.3:
                logger.warning(f"[DIAG] Very short audio ({duration_sec:.3f}s) — likely cause of 'no speech detected'")
            if sample_width != 2:
                logger.warning(f"[DIAG] Unexpected sample width {sample_width} bytes (expected 2 for 16-bit PCM) — may cause ASR mismatch")

        if not settings.nvidia_asr_function_id:
            raise ValueError("Parakeet ASR not configured - set NVIDIA_ASR_FUNCTION_ID")

        if settings.debug:
            masked_fn = settings.nvidia_asr_function_id[:-4] + "****" if len(settings.nvidia_asr_function_id) > 4 else "****"
            logger.info(f"[DIAG] ASR config: uri={settings.nvidia_asr_grpc_uri}, lang={settings.nvidia_asr_language_code}, fn_id={masked_fn}")

        auth = Auth(
            uri=settings.nvidia_asr_grpc_uri,
            use_ssl=True,
            metadata_args=[
                ["function-id", settings.nvidia_asr_function_id],
                ["authorization", f"Bearer {settings.nvidia_api_key}"],
            ],
        )

        asr_service = ASRService(auth)

        config = riva_asr_pb2.RecognitionConfig(
            encoding=AudioEncoding.LINEAR_PCM,
            sample_rate_hertz=frame_rate,
            language_code=settings.nvidia_asr_language_code,
            max_alternatives=1,
        )

        response = asr_service.offline_recognize(
            audio_bytes=audio_bytes,
            config=config,
        )

        if settings.debug:
            has_results = bool(response.results)
            has_alts = bool(response.results[0].alternatives) if response.results else False
            logger.info(f"[DIAG] Response: has_results={has_results}, has_alternatives={has_alts}")

        if response.results and response.results[0].alternatives:
            transcript = response.results[0].alternatives[0].transcript.strip()
        else:
            transcript = ""

        if not transcript:
            if not response.results:
                raise ValueError("No speech detected in recording. Please speak clearly and try again.")
            else:
                raise ValueError("Could not transcribe recording. Try speaking more clearly or louder.")

        return transcript

    except ValueError:
        raise
    except Exception as e:
        error_str = str(e)
        if "deadline" in error_str.lower():
            raise ValueError("Transcription timed out (exceeded 30 seconds)")
        elif "authentication" in error_str.lower() or "unauthorized" in error_str.lower():
            raise ValueError(
                "Parakeet authentication failed - check NVIDIA_API_KEY and NVIDIA_ASR_FUNCTION_ID"
            )
        else:
            raise ValueError(f"Transcription failed: {error_str}")

    finally:
        if wav_path != audio_file_path and os.path.exists(wav_path):
            os.remove(wav_path)


def _transcode_to_wav(audio_file_path: str) -> str:
    """Transcode audio file to 16-bit mono 16kHz WAV.

    Args:
        audio_file_path: Path to audio file (.mp3, .m4a, .webm, etc.)

    Returns:
        Path to transcoded WAV file (caller must delete)

    Raises:
        ValueError: If transcoding fails
    """
    try:
        if settings.debug:
            ffmpeg_path = shutil.which("ffmpeg")
            logger.info(f"[DIAG] ffmpeg location: {ffmpeg_path}")

        audio = AudioSegment.from_file(audio_file_path)
        audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)

        if settings.debug:
            logger.info(f"[DIAG] Loaded audio: duration={len(audio)}ms, channels=1, sample_width={audio.sample_width} bytes, frame_rate=16000 (all after conversion to 16-bit mono 16kHz)")

        fd, wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        audio.export(wav_path, format="wav")
        return wav_path

    except Exception as e:
        raise ValueError(f"Unsupported or corrupt audio format: {e}")
