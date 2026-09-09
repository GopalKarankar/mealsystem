import pytest
import tempfile
import os
import httpx
from unittest.mock import patch, MagicMock
from groq import (
    GroqError, AuthenticationError, RateLimitError, APIStatusError,
    APITimeoutError, APIConnectionError
)
from meals.services.vision_service import scan_image
from meals.services.llm_service import LLMServiceError


def _create_status_error(status_code, message):
    """Helper to construct a groq APIStatusError with a status code."""
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(status_code, request=request)
    # APIStatusError is a base class; we construct it directly for generic status errors
    return APIStatusError(message, response=response, body=None)


@pytest.mark.django_db
class TestVisionServiceRetry:
    """Test vision service retry logic on transient Groq errors."""

    def create_temp_image(self):
        """Create a temporary test image file."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            f.write(b'\xff\xd8\xff' + b'fake jpeg data')
            return f.name

    def test_scan_image_retries_on_503_error(self):
        """Test that scan_image retries on 503 Groq errors (using typed APIStatusError)."""
        image_path = self.create_temp_image()
        try:
            attempt_count = 0

            def mock_chat_completions(*args, **kwargs):
                nonlocal attempt_count
                attempt_count += 1
                if attempt_count <= 2:
                    # Fail first 2 attempts with 503 error (typed)
                    raise _create_status_error(503, "Service is over capacity")
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
                raise _create_status_error(503, "Service is over capacity")

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
        """Test that scan_image retries on 429 rate limit errors (using typed RateLimitError)."""
        image_path = self.create_temp_image()
        try:
            attempt_count = 0

            def mock_chat_completions(*args, **kwargs):
                nonlocal attempt_count
                attempt_count += 1
                if attempt_count == 1:
                    raise _create_status_error(429, "Rate limit exceeded")
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
        """Test that scan_image does NOT retry on 401 auth errors (using typed AuthenticationError)."""
        image_path = self.create_temp_image()
        try:
            attempt_count = 0

            def mock_chat_completions(*args, **kwargs):
                nonlocal attempt_count
                attempt_count += 1
                request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
                response = httpx.Response(401, request=request)
                raise AuthenticationError("Authentication failed", response=response, body=None)

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
                raise _create_status_error(413, "Request entity too large")

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

    def test_scan_image_retries_on_real_timeout_error(self):
        """Test that scan_image retries on real APITimeoutError (the regression test for the bug fix)."""
        image_path = self.create_temp_image()
        try:
            attempt_count = 0

            def mock_chat_completions(*args, **kwargs):
                nonlocal attempt_count
                attempt_count += 1
                if attempt_count <= 2:
                    # Fail first 2 attempts with real APITimeoutError
                    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
                    raise APITimeoutError(request=request)
                # Succeed on 3rd attempt
                response = MagicMock()
                response.choices[0].message.content = "a sandwich with fries"
                return response

            with patch('meals.services.vision_service.Groq') as mock_groq:
                mock_groq_instance = MagicMock()
                mock_groq.return_value = mock_groq_instance
                mock_groq_instance.chat.completions.create = mock_chat_completions

                result = scan_image(image_path)
                assert result == "a sandwich with fries"
                assert attempt_count == 3  # Retried twice, succeeded on third

        finally:
            if os.path.exists(image_path):
                os.remove(image_path)

    def test_scan_image_raises_llm_service_error_after_timeout_retries_exhausted(self):
        """Test that scan_image returns 503 (LLMServiceError) after timeout retries exhausted."""
        image_path = self.create_temp_image()
        try:
            def mock_chat_completions(*args, **kwargs):
                request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
                raise APITimeoutError(request=request)

            with patch('meals.services.vision_service.Groq') as mock_groq:
                mock_groq_instance = MagicMock()
                mock_groq.return_value = mock_groq_instance
                mock_groq_instance.chat.completions.create = mock_chat_completions

                with pytest.raises(LLMServiceError) as exc_info:
                    scan_image(image_path)

                # Should be LLMServiceError (503), not ValueError (422)
                assert "timed out" in str(exc_info.value).lower()

        finally:
            if os.path.exists(image_path):
                os.remove(image_path)

    def test_scan_image_retries_on_connection_error(self):
        """Test that scan_image retries on generic APIConnectionError (non-timeout)."""
        image_path = self.create_temp_image()
        try:
            attempt_count = 0

            def mock_chat_completions(*args, **kwargs):
                nonlocal attempt_count
                attempt_count += 1
                if attempt_count == 1:
                    # Fail once with connection error
                    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
                    raise APIConnectionError(message="Connection refused", request=request)
                # Succeed on 2nd attempt
                response = MagicMock()
                response.choices[0].message.content = "a salad"
                return response

            with patch('meals.services.vision_service.Groq') as mock_groq:
                mock_groq_instance = MagicMock()
                mock_groq.return_value = mock_groq_instance
                mock_groq_instance.chat.completions.create = mock_chat_completions

                result = scan_image(image_path)
                assert result == "a salad"
                assert attempt_count == 2  # Retried once

        finally:
            if os.path.exists(image_path):
                os.remove(image_path)
