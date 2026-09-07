# Fix: `ModuleNotFoundError: No module named 'riva.client'`

## Quick Reference

**Error**: `ModuleNotFoundError: No module named 'riva.client'` when running backend (backend/app/services/whisper_service.py line 4).

**Root cause**: The wrong PyPI package (`riva` v0.3.19, an "AI Agent Command Center" tool) is installed in `backend/venv` and squats the top-level `riva` import namespace. The correct package (`nvidia-riva-client==2.17.0`) is listed in `requirements.txt` but was never installed.

**Status**: Environment/install defect — no code changes needed. `backend/requirements.txt`, `config.py`, and `whisper_service.py` are all correctly wired already (per the earlier Parakeet migration in `docs/parakeet-stt-swap-prompt.md`).

---

## Diagnosis

### Symptom Chain
1. **Import chain fails**: `routes/meals.py` → `meal_service.py:9` (imports `whisper_service`) → `whisper_service.py:4` (imports `riva.client`).
2. **Affected code paths**: Any voice meal ingestion (`POST /meals/voice`), plus test collection for `tests/test_whisper_service.py` and `tests/test_meal_service.py`.
3. **Error message**: `ModuleNotFoundError: No module named 'riva.client'` — indicates the `riva` package has no `client` submodule.

### Root Cause Analysis
Two packages on PyPI collide at the top-level `riva` namespace:
1. **Installed (wrong)**: `riva==0.3.19` — AI Agent Command Center (a monitoring/discovery tool for AI coding agents).
   - Package name: `riva` (PyPI project name)
   - Import name: `riva`
   - Structure: `riva/__init__.py` (CLI/dashboard only, no `client` submodule)
   - Homepage: https://github.com/sarkar-ai-taken/riva

2. **Required (missing)**: `nvidia-riva-client==2.17.0` — NVIDIA's official Python client for Riva/Parakeet gRPC services.
   - Package name: `nvidia-riva-client` (PyPI project name)
   - Import name: `riva` (top-level module, but from NVIDIA's package)
   - Structure: `riva/client/` (gRPC client code), `riva/client/proto/` (Parakeet ASR protocol buffers)
   - Provides: `Auth`, `ASRService`, `riva.client.proto.riva_asr_pb2` (used in `whisper_service.py:4-5`)

**Why this happened**: Someone (or a prior session) likely installed the wrong package by name, or a dependency pulled in the unrelated `riva` tool. When both packages compete for the `riva` module, the first one installed wins the namespace.

**Verification in venv**:
```powershell
cd backend
venv\Scripts\pip.exe show nvidia-riva-client
# → WARNING: Package(s) not found: nvidia-riva-client

venv\Scripts\pip.exe show riva
# → Name: riva
#   Version: 0.3.19
#   Summary: AI Agent Command Center - discover and monitor AI coding agents...
```

---

## Fix

### 1. Remove the Wrong Package

```powershell
cd backend
venv\Scripts\pip.exe uninstall riva -y
```

### 2. Install the Correct Package

```powershell
venv\Scripts\pip.exe install nvidia-riva-client==2.17.0
```

This also pulls required transitive deps: `grpcio`, `protobuf`, and NVIDIA's Riva protocol buffer definitions.

---

## Verification

### Confirm Installation

```powershell
cd backend
venv\Scripts\pip.exe show nvidia-riva-client
# Should output package metadata for NVIDIA's client, not the AI-Agent-Command-Center tool
```

### Verify Import Works

```powershell
venv\Scripts\python.exe -c "import riva.client; from riva.client import Auth, ASRService; from riva.client.proto import riva_asr_pb2; print('Import OK')"
# Expected: "Import OK"
```

### Run Backend App

```powershell
cd backend
python main.py
# Should start without ModuleNotFoundError: No module named 'riva.client'
# The app will be ready at http://localhost:8000
```

### Run Tests (Optional)

```powershell
cd backend
# Install test dependencies first (if needed):
# venv\Scripts\pip.exe install pytest pytest-asyncio

venv\Scripts\python.exe -m pytest tests/test_whisper_service.py tests/test_meal_service.py -v
# Expected: Tests collect successfully and pass.
# (These tests mock Auth/ASRService, so no real NVIDIA API key required.)
```

### Optional: Quick API Test

```powershell
cd backend
# Start backend: python main.py
# In another terminal, try a voice upload (requires a valid JWT token):
# curl -X POST http://localhost:8000/meals/voice \
#   -H "Authorization: Bearer <your_jwt_token>" \
#   -F "audio=@sample_meal.wav"
# Should no longer fail with ModuleNotFoundError.
```

---

## Prevention

1. **Verify package names explicitly** when installing Riva-related dependencies — use `pip show <package_name>`, not just the import name:
   ```powershell
   pip show nvidia-riva-client  # Verify the NVIDIA client is installed, not 'riva'
   ```

2. **Rely on `requirements.txt` as source of truth**:
   ```
   nvidia-riva-client==2.17.0
   pydub==0.25.1  # For audio transcoding (non-WAV → WAV)
   ```
   Always re-run `pip install -r requirements.txt` after pulling code, rather than installing packages by import name.

3. **Test import early** — the Parakeet swap doc (`docs/parakeet-stt-swap-prompt.md`) already anticipated this exact failure mode in its testing checklist:
   ```
   - [ ] nvidia-riva-client installed: pip list | grep nvidia-riva-client
   ```

---

## Related Documentation

- **Parakeet/Riva integration design**: `docs/parakeet-stt-swap-prompt.md` — covers the full gRPC integration, config, audio transcoding, and testing strategy.
- **Affected code**:
  - `backend/app/services/whisper_service.py` — uses `riva.client.Auth`, `ASRService`, and `riva.client.proto.riva_asr_pb2`
  - `backend/app/services/meal_service.py:9` — imports `whisper_service`, triggering the transitive import
  - `backend/app/routes/meals.py:62` — POST /meals/voice endpoint calls `whisper_service.transcribe()`
- **Config**: `backend/app/config.py` defines `nvidia_asr_function_id`, `nvidia_asr_grpc_uri`, `nvidia_asr_language_code` (all set correctly; no changes needed).

---

## Troubleshooting

**Q: Still getting `ModuleNotFoundError` after running the fix?**
- Verify `pip show nvidia-riva-client` works and shows version 2.17.0.
- Check that your IDE or test runner is using the correct Python interpreter: `venv\Scripts\python.exe`, not system Python.
- In VS Code / PyCharm, restart the Python language server after venv changes.

**Q: `pip install nvidia-riva-client==2.17.0` fails with a network error?**
- Check internet connectivity.
- Verify PyPI is accessible: `pip list` should work.
- Try `pip install --upgrade pip` first, then retry.

**Q: `pip uninstall riva` says "Package not found"?**
- The wrong package may have already been removed. Run `pip show nvidia-riva-client` to confirm the correct one is installed.

**Q: Tests pass but `POST /meals/voice` still fails?**
- Ensure `NVIDIA_ASR_FUNCTION_ID` is set in `backend/.env` (get from https://build.nvidia.com after signing up for NVIDIA API access).
- Verify `NVIDIA_API_KEY` is also set and valid.
- Check backend logs for the actual gRPC error (may be auth or model-not-found).
- This doc fixes the *import* error; runtime errors on the actual transcription are different issues (see `docs/parakeet-stt-swap-prompt.md` § Troubleshooting).
