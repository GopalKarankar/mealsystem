import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock
from groq import GroqError
from meals.services.vision_service import scan_image
from meals.services.llm_service import LLMServiceError


@pytest.mark.django_db
class TestVisionServiceRetry:
    """Test vision service retry logic on transient Groq errors."""

    def create_temp_image(self):
        """Create a temporary test image file."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            f.write(b'\xff\xd8\xff' + b'fake jpeg data')
            return f.name

    def test_scan_image_retries_on_503_error(self):
        """Test that scan_image retries on 503 Groq errors."""
        image_path = self.create_temp_image()
        try:
            attempt_count = 0

            def mock_chat_completions(*args, **kwargs):
                nonlocal attempt_count
                attempt_count += 1
                if attempt_count <= 2:
                    # Fail first 2 attempts with 503 error
                    raise GroqError("Error code: 503 - service is over capacity")
                # Succeed on 3rd attempt
                response = MagicMock()
                response.choices[0].message.content = "a banana on a plate"
                return response

            with patch('meals.services.vision_service.Groq') as mock_groq:
                mock_groq_instance = MagicMock()
                mock_groq.return_value = mock_groq_instance
                mock_groq_instance.chat.completions.create = mock_chat_completions

                result = scan_image(image_path)
                assert result == "a banana on a plate"
                assert attempt_count == 3  # Failed twice, succeeded on third

        finally:
            if os.path.exists(image_path):
                os.remove(image_path)

    def test_scan_image_raises_llm_service_error_on_exhausted_retries(self):
        """Test that scan_image raises LLMServiceError after retries exhausted."""
        image_path = self.create_temp_image()
        try:
            def mock_chat_completions(*args, **kwargs):
                raise GroqError("Error code: 503 - service is over capacity")

            with patch('meals.services.vision_service.Groq') as mock_groq:
                mock_groq_instance = MagicMock()
                mock_groq.return_value = mock_groq_instance
                mock_groq_instance.chat.completions.create = mock_chat_completions

                with pytest.raises(LLMServiceError) as exc_info:
                    scan_image(image_path)

                assert "overloaded" in str(exc_info.value).lower()

        finally:
            if os.path.exists(image_path):
                os.remove(image_path)

    def test_scan_image_retries_on_rate_limit_error(self):
        """Test that scan_image retries on 429 rate limit errors."""
        image_path = self.create_temp_image()
        try:
            attempt_count = 0

            def mock_chat_completions(*args, **kwargs):
                nonlocal attempt_count
                attempt_count += 1
                if attempt_count == 1:
                    raise GroqError("Error code: 429 - rate limit exceeded")
                # Succeed on 2nd attempt
                response = MagicMock()
                response.choices[0].message.content = "a bowl of pasta"
                return response

            with patch('meals.services.vision_service.Groq') as mock_groq:
                mock_groq_instance = MagicMock()
                mock_groq.return_value = mock_groq_instance
                mock_groq_instance.chat.completions.create = mock_chat_completions

                result = scan_image(image_path)
                assert result == "a bowl of pasta"
                assert attempt_count == 2

        finally:
            if os.path.exists(image_path):
                os.remove(image_path)

    def test_scan_image_no_retry_on_auth_error(self):
        """Test that scan_image does NOT retry on 401 auth errors."""
        image_path = self.create_temp_image()
        try:
            attempt_count = 0

            def mock_chat_completions(*args, **kwargs):
                nonlocal attempt_count
                attempt_count += 1
                raise GroqError("Error code: 401 - authentication failed")

            with patch('meals.services.vision_service.Groq') as mock_groq:
                mock_groq_instance = MagicMock()
                mock_groq.return_value = mock_groq_instance
                mock_groq_instance.chat.completions.create = mock_chat_completions

                with pytest.raises(ValueError) as exc_info:
                    scan_image(image_path)

                assert "authentication" in str(exc_info.value).lower()
                assert attempt_count == 1  # No retry

        finally:
            if os.path.exists(image_path):
                os.remove(image_path)

    def test_scan_image_no_retry_on_413_error(self):
        """Test that scan_image does NOT retry on 413 payload-too-large errors."""
        image_path = self.create_temp_image()
        try:
            attempt_count = 0

            def mock_chat_completions(*args, **kwargs):
                nonlocal attempt_count
                attempt_count += 1
                raise GroqError("Error code: 413 - request entity too large")

            with patch('meals.services.vision_service.Groq') as mock_groq:
                mock_groq_instance = MagicMock()
                mock_groq.return_value = mock_groq_instance
                mock_groq_instance.chat.completions.create = mock_chat_completions

                with pytest.raises(ValueError) as exc_info:
                    scan_image(image_path)

                assert "too large" in str(exc_info.value).lower()
                assert attempt_count == 1  # No retry

        finally:
            if os.path.exists(image_path):
                os.remove(image_path)
