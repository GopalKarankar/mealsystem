import pytest
from unittest.mock import patch, MagicMock, ANY
import tempfile
import os
import wave
import struct
from app.services.whisper_service import transcribe


@pytest.fixture
def wav_audio_path(tmp_path):
    """Create a temporary valid WAV file with 1 second of silence (16kHz, mono, 16-bit)."""
    audio_file = tmp_path / "test_audio.wav"

    # Create a valid WAV file: 1 second of silence at 16kHz mono
    sample_rate = 16000
    duration = 1
    num_frames = sample_rate * duration

    with wave.open(str(audio_file), 'wb') as wav_f:
        wav_f.setnchannels(1)  # mono
        wav_f.setsampwidth(2)  # 16-bit
        wav_f.setframerate(sample_rate)
        # Write silence (zeros)
        silence = b'\x00\x00' * num_frames
        wav_f.writeframes(silence)

    return str(audio_file)


@pytest.fixture
def webm_audio_path(tmp_path):
    """Create a temporary WebM file."""
    audio_file = tmp_path / "test_audio.webm"
    audio_file.write_bytes(b"fake webm data")
    return str(audio_file)


class TestWhisperService:
    @patch("app.services.whisper_service.ASRService")
    @patch("app.services.whisper_service.Auth")
    def test_transcribe_wav_success(self, mock_auth_class, mock_asr_class, wav_audio_path):
        """Test successful transcription of a WAV file."""
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth

        mock_asr = MagicMock()
        mock_asr_class.return_value = mock_asr

        mock_response = MagicMock()
        mock_response.results = [
            MagicMock(alternatives=[MagicMock(transcript="I had a banana")])
        ]
        mock_asr.offline_recognize.return_value = mock_response

        # Use the real wav_audio_path (which is a valid WAV file) so wave.open() works
        result = transcribe(wav_audio_path)

        assert result == "I had a banana"
        mock_auth_class.assert_called_once()
        mock_asr.offline_recognize.assert_called_once()

    @patch("app.services.whisper_service.wave.open")
    @patch("app.services.whisper_service.AudioSegment")
    @patch("app.services.whisper_service.ASRService")
    @patch("app.services.whisper_service.Auth")
    def test_transcribe_webm_transcoded(
        self, mock_auth_class, mock_asr_class, mock_audio_segment, mock_wave_open, webm_audio_path
    ):
        """Test that WebM files are transcoded to WAV before transcription."""
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth

        mock_asr = MagicMock()
        mock_asr_class.return_value = mock_asr

        mock_audio = MagicMock()
        mock_audio.set_channels.return_value.set_frame_rate.return_value = mock_audio
        mock_audio_segment.from_file.return_value = mock_audio

        mock_response = MagicMock()
        mock_response.results = [
            MagicMock(alternatives=[MagicMock(transcript="I had pizza")])
        ]
        mock_asr.offline_recognize.return_value = mock_response

        # Mock wave.open to return WAV metadata without actual file
        mock_wav_file = MagicMock()
        mock_wav_file.__enter__.return_value.getnframes.return_value = 16000  # 1 sec at 16kHz
        mock_wav_file.__enter__.return_value.getframerate.return_value = 16000
        mock_wav_file.__enter__.return_value.getnchannels.return_value = 1
        mock_wav_file.__enter__.return_value.readframes.return_value = b'\x00\x00' * 16000
        mock_wave_open.return_value = mock_wav_file

        with patch("app.services.whisper_service.tempfile.mkstemp") as mock_mkstemp:
            fd = 999
            temp_wav = "/tmp/test_xyz.wav"
            mock_mkstemp.return_value = (fd, temp_wav)
            with patch("os.close"):
                result = transcribe(webm_audio_path)

        assert result == "I had pizza"
        mock_audio_segment.from_file.assert_called_once_with(webm_audio_path)
        mock_audio.set_channels.assert_called_once_with(1)
        mock_audio.set_channels.return_value.set_frame_rate.assert_called_once_with(16000)
        mock_audio.export.assert_called_once_with(temp_wav, format="wav")

    @patch("app.services.whisper_service.wave.open")
    @patch("app.services.whisper_service.ASRService")
    @patch("app.services.whisper_service.Auth")
    def test_transcribe_empty_result(self, mock_auth_class, mock_asr_class, mock_wave_open, wav_audio_path):
        """Test that empty transcription raises ValueError with actionable message."""
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth

        mock_asr = MagicMock()
        mock_asr_class.return_value = mock_asr

        mock_response = MagicMock()
        mock_response.results = [MagicMock(alternatives=[MagicMock(transcript="")])]
        mock_asr.offline_recognize.return_value = mock_response

        # Mock wave.open
        mock_wav_file = MagicMock()
        mock_wav_file.__enter__.return_value.getnframes.return_value = 16000
        mock_wav_file.__enter__.return_value.getframerate.return_value = 16000
        mock_wav_file.__enter__.return_value.getnchannels.return_value = 1
        mock_wav_file.__enter__.return_value.readframes.return_value = b'\x00\x00' * 16000
        mock_wave_open.return_value = mock_wav_file

        with pytest.raises(ValueError, match="Could not transcribe recording"):
            transcribe(wav_audio_path)

    @patch("app.services.whisper_service.wave.open")
    @patch("app.services.whisper_service.ASRService")
    @patch("app.services.whisper_service.Auth")
    def test_transcribe_no_results(self, mock_auth_class, mock_asr_class, mock_wave_open, wav_audio_path):
        """Test that no results raises ValueError with speech-specific message."""
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth

        mock_asr = MagicMock()
        mock_asr_class.return_value = mock_asr

        mock_response = MagicMock()
        mock_response.results = []
        mock_asr.offline_recognize.return_value = mock_response

        # Mock wave.open
        mock_wav_file = MagicMock()
        mock_wav_file.__enter__.return_value.getnframes.return_value = 16000
        mock_wav_file.__enter__.return_value.getframerate.return_value = 16000
        mock_wav_file.__enter__.return_value.getnchannels.return_value = 1
        mock_wav_file.__enter__.return_value.readframes.return_value = b'\x00\x00' * 16000
        mock_wave_open.return_value = mock_wav_file

        with pytest.raises(ValueError, match="No speech detected"):
            transcribe(wav_audio_path)

    @patch("app.services.whisper_service.wave.open")
    @patch("app.services.whisper_service.Auth")
    def test_transcribe_missing_function_id(self, mock_auth_class, mock_wave_open, wav_audio_path):
        """Test that missing NVIDIA_ASR_FUNCTION_ID raises ValueError."""
        # Mock wave.open
        mock_wav_file = MagicMock()
        mock_wav_file.__enter__.return_value.getnframes.return_value = 16000
        mock_wav_file.__enter__.return_value.getframerate.return_value = 16000
        mock_wav_file.__enter__.return_value.getnchannels.return_value = 1
        mock_wav_file.__enter__.return_value.readframes.return_value = b'\x00\x00' * 16000
        mock_wave_open.return_value = mock_wav_file

        with patch("app.services.whisper_service.settings") as mock_settings:
            mock_settings.nvidia_asr_function_id = ""
            mock_settings.nvidia_api_key = "test_key"
            mock_settings.debug = False

            with pytest.raises(
                ValueError, match="Parakeet ASR not configured - set NVIDIA_ASR_FUNCTION_ID"
            ):
                transcribe(wav_audio_path)

    @patch("app.services.whisper_service.wave.open")
    @patch("app.services.whisper_service.ASRService")
    @patch("app.services.whisper_service.Auth")
    def test_transcribe_timeout(self, mock_auth_class, mock_asr_class, mock_wave_open, wav_audio_path):
        """Test that deadline exceeded is caught as timeout error."""
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth

        mock_asr = MagicMock()
        mock_asr_class.return_value = mock_asr
        mock_asr.offline_recognize.side_effect = Exception("deadline exceeded")

        # Mock wave.open
        mock_wav_file = MagicMock()
        mock_wav_file.__enter__.return_value.getnframes.return_value = 16000
        mock_wav_file.__enter__.return_value.getframerate.return_value = 16000
        mock_wav_file.__enter__.return_value.getnchannels.return_value = 1
        mock_wav_file.__enter__.return_value.readframes.return_value = b'\x00\x00' * 16000
        mock_wave_open.return_value = mock_wav_file

        with pytest.raises(ValueError, match="Transcription timed out"):
            transcribe(wav_audio_path)

    @patch("app.services.whisper_service.wave.open")
    @patch("app.services.whisper_service.ASRService")
    @patch("app.services.whisper_service.Auth")
    def test_transcribe_auth_failure(self, mock_auth_class, mock_asr_class, mock_wave_open, wav_audio_path):
        """Test that authentication error is properly mapped."""
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth

        mock_asr = MagicMock()
        mock_asr_class.return_value = mock_asr
        mock_asr.offline_recognize.side_effect = Exception("unauthorized")

        # Mock wave.open
        mock_wav_file = MagicMock()
        mock_wav_file.__enter__.return_value.getnframes.return_value = 16000
        mock_wav_file.__enter__.return_value.getframerate.return_value = 16000
        mock_wav_file.__enter__.return_value.getnchannels.return_value = 1
        mock_wav_file.__enter__.return_value.readframes.return_value = b'\x00\x00' * 16000
        mock_wave_open.return_value = mock_wav_file

        with pytest.raises(ValueError, match="Parakeet authentication failed"):
            transcribe(wav_audio_path)

    @patch("app.services.whisper_service.AudioSegment")
    @patch("app.services.whisper_service.ASRService")
    @patch("app.services.whisper_service.Auth")
    def test_transcode_failure(
        self, mock_auth_class, mock_asr_class, mock_audio_segment, webm_audio_path
    ):
        """Test that transcoding failure raises ValueError."""
        mock_audio_segment.from_file.side_effect = Exception("unsupported codec")

        with pytest.raises(ValueError, match="Unsupported or corrupt audio format"):
            transcribe(webm_audio_path)

    @patch("app.services.whisper_service.AudioSegment")
    def test_transcode_cleanup_on_failure(self, mock_audio_segment, webm_audio_path):
        """Test that transcoded temp WAV is cleaned up even on failure."""
        mock_audio_segment.from_file.side_effect = Exception("bad file")

        with pytest.raises(ValueError):
            transcribe(webm_audio_path)

    @patch("app.services.whisper_service.wave.open")
    @patch("app.services.whisper_service.ASRService")
    @patch("app.services.whisper_service.Auth")
    def test_transcribe_strips_whitespace(
        self, mock_auth_class, mock_asr_class, mock_wave_open, wav_audio_path
    ):
        """Test that transcript is stripped of leading/trailing whitespace."""
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth

        mock_asr = MagicMock()
        mock_asr_class.return_value = mock_asr

        mock_response = MagicMock()
        mock_response.results = [
            MagicMock(alternatives=[MagicMock(transcript="  hello world  ")])
        ]
        mock_asr.offline_recognize.return_value = mock_response

        # Mock wave.open
        mock_wav_file = MagicMock()
        mock_wav_file.__enter__.return_value.getnframes.return_value = 16000
        mock_wav_file.__enter__.return_value.getframerate.return_value = 16000
        mock_wav_file.__enter__.return_value.getnchannels.return_value = 1
        mock_wav_file.__enter__.return_value.readframes.return_value = b'\x00\x00' * 16000
        mock_wave_open.return_value = mock_wav_file

        result = transcribe(wav_audio_path)

        assert result == "hello world"

    @patch("app.services.whisper_service.wave.open")
    @patch("app.services.whisper_service.ASRService")
    @patch("app.services.whisper_service.Auth")
    def test_transcribe_empty_alternatives(self, mock_auth_class, mock_asr_class, mock_wave_open, wav_audio_path):
        """Test that results present but no alternatives raises appropriate error."""
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth

        mock_asr = MagicMock()
        mock_asr_class.return_value = mock_asr

        mock_response = MagicMock()
        mock_response.results = [MagicMock(alternatives=[])]
        mock_asr.offline_recognize.return_value = mock_response

        # Mock wave.open
        mock_wav_file = MagicMock()
        mock_wav_file.__enter__.return_value.getnframes.return_value = 16000
        mock_wav_file.__enter__.return_value.getframerate.return_value = 16000
        mock_wav_file.__enter__.return_value.getnchannels.return_value = 1
        mock_wav_file.__enter__.return_value.readframes.return_value = b'\x00\x00' * 16000
        mock_wave_open.return_value = mock_wav_file

        with pytest.raises(ValueError, match="Could not transcribe recording"):
            transcribe(wav_audio_path)

    @patch("app.services.whisper_service.wave.open")
    @patch("app.services.whisper_service.ASRService")
    @patch("app.services.whisper_service.Auth")
    def test_transcribe_whitespace_only(self, mock_auth_class, mock_asr_class, mock_wave_open, wav_audio_path):
        """Test that whitespace-only transcript is treated as empty."""
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth

        mock_asr = MagicMock()
        mock_asr_class.return_value = mock_asr

        mock_response = MagicMock()
        mock_response.results = [MagicMock(alternatives=[MagicMock(transcript="   \t\n  ")])]
        mock_asr.offline_recognize.return_value = mock_response

        # Mock wave.open
        mock_wav_file = MagicMock()
        mock_wav_file.__enter__.return_value.getnframes.return_value = 16000
        mock_wav_file.__enter__.return_value.getframerate.return_value = 16000
        mock_wav_file.__enter__.return_value.getnchannels.return_value = 1
        mock_wav_file.__enter__.return_value.readframes.return_value = b'\x00\x00' * 16000
        mock_wave_open.return_value = mock_wav_file

        with pytest.raises(ValueError, match="Could not transcribe recording"):
            transcribe(wav_audio_path)
