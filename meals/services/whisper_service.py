import logging
import os
import shutil
import tempfile
import wave
from riva.client import Auth, ASRService, AudioEncoding
from riva.client.proto import riva_asr_pb2
from pydub import AudioSegment
from django.conf import settings

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

        if settings.DEBUG:
            file_size = os.path.getsize(audio_file_path)
            logger.info(f"[DIAG] Input: {audio_file_path}, ext={ext}, size={file_size} bytes")

        if ext != ".wav":
            wav_path = _transcode_to_wav(audio_file_path)
            if settings.DEBUG and os.path.exists(wav_path):
                wav_size = os.path.getsize(wav_path)
                logger.info(f"[DIAG] Transcoded WAV: size={wav_size} bytes")

        with wave.open(wav_path, "rb") as wf:
            num_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            framerate = wf.getframerate()

            expected_framerate = 16000
            if framerate != expected_framerate:
                logger.warning(
                    f"[DIAG] Warning: input WAV has {framerate}Hz, Parakeet expects {expected_framerate}Hz"
                )

            audio_data = wf.readframes(wf.getnframes())

        auth = Auth(uri=settings.NVIDIA_ASR_GRPC_URI)
        auth.generate_grpc_metadata(settings.NVIDIA_API_KEY)

        asr_service = ASRService(settings.NVIDIA_ASR_GRPC_URI, auth)

        recognition_config = riva_asr_pb2.RecognitionConfig()
        recognition_config.encoding = AudioEncoding.LINEAR_PCM
        recognition_config.sample_rate_hertz = framerate
        recognition_config.language_code = settings.NVIDIA_ASR_LANGUAGE_CODE
        recognition_config.max_alternative = 1

        response = asr_service.recognize(audio_data, recognition_config, grpc_metadata=auth.metadata)

        if response.results and response.results[0].alternatives:
            transcript = response.results[0].alternatives[0].transcript
            if settings.DEBUG:
                logger.info(f"[DIAG] Transcribed: {transcript[:100]}...")
            return transcript
        else:
            return ""

    except Exception as e:
        error_msg = str(e)
        logger.error(f"[DIAG] Whisper error: {error_msg}")
        if "401" in error_msg or "authentication" in error_msg.lower():
            raise ValueError("NVIDIA API authentication failed: invalid API key")
        elif "timeout" in error_msg.lower() or "deadline" in error_msg.lower():
            raise ValueError("Audio transcription timed out; please try a shorter recording")
        elif "unsupported" in error_msg.lower():
            raise ValueError("Audio format or codec not supported")
        else:
            raise ValueError(f"Audio transcription failed: {error_msg}")
    finally:
        if wav_path != audio_file_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp WAV: {e}")


def _transcode_to_wav(input_path: str) -> str:
    """Transcode audio to 16-bit mono 16kHz WAV using ffmpeg/pydub.

    Args:
        input_path: Path to source audio file

    Returns:
        Path to temporary transcoded WAV file
    """
    try:
        audio = AudioSegment.from_file(input_path)

        audio = audio.set_channels(1)
        audio = audio.set_frame_rate(16000)
        audio = audio.set_sample_width(2)

        fd, temp_wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        audio.export(temp_wav_path, format="wav")

        if settings.DEBUG:
            logger.info(f"[DIAG] Transcoded to WAV: {temp_wav_path}")

        return temp_wav_path
    except Exception as e:
        logger.error(f"[DIAG] Transcode error: {e}")
        raise ValueError(f"Failed to transcode audio: {e}")
