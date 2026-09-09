import pytest
import tempfile
import os
import httpx
from unittest.mock import patch, MagicMock
from google.genai import errors
from meals.services.vision_service import scan_image
from meals.services.llm_service import LLMServiceError


def _create_client_error(status_code, message):
    """Helper to construct a google.genai ClientError with a status code."""
    error = errors.ClientError(message, response_json={"error": {"message": message}})
    error.code = status_code
    return error


def _create_server_error(status_code, message):
    """Helper to construct a google.genai ServerError with a status code."""
    error = errors.ServerError(message, response_json={"error": {"message": message}})
    error.code = status_code
    return error


@pytest.mark.django_db
class TestVisionServiceRetry:
    """Test vision service retry logic on transient Gemini errors."""

    def create_temp_image(self):
        """Create a temporary test image file."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            f.write(b'\xff\xd8\xff' + b'fake jpeg data')
            return f.name

    def test_scan_image_retries_on_503_error(self):
        """Test that scan_image retries on 503 server errors."""
        image_path = self.create_temp_image()
        try:
            attempt_count = 0

            def mock_generate_content(*args, **kwargs):
                nonlocal attempt_count
                attempt_count += 1
                if attempt_count <= 2:
                    # Fail first 2 attempts with 503 error
                    raise _create_server_error(503, "Service is over capacity")
                # Succeed on 3rd attempt
                response = MagicMock()
                response.text = "a banana on a plate"
                return response

            with patch('meals.services.vision_service.genai.Client') as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.models.generate_content = mock_generate_content

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
            def mock_generate_content(*args, **kwargs):
                raise _create_server_error(503, "Service is over capacity")

            with patch('meals.services.vision_service.genai.Client') as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.models.generate_content = mock_generate_content

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

            def mock_generate_content(*args, **kwargs):
                nonlocal attempt_count
                attempt_count += 1
                if attempt_count == 1:
                    raise _create_client_error(429, "Rate limit exceeded")
                # Succeed on 2nd attempt
                response = MagicMock()
                response.text = "a bowl of pasta"
                return response

            with patch('meals.services.vision_service.genai.Client') as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.models.generate_content = mock_generate_content

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

            def mock_generate_content(*args, **kwargs):
                nonlocal attempt_count
                attempt_count += 1
                raise _create_client_error(401, "Authentication failed")

            with patch('meals.services.vision_service.genai.Client') as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.models.generate_content = mock_generate_content

                with pytest.raises(ValueError) as exc_info:
                    scan_image(image_path)

                assert "authentication" in str(exc_info.value).lower()
                assert attempt_count == 1  # No retry

        finally:
            if os.path.exists(image_path):
                os.remove(image_path)

    def test_scan_image_no_retry_on_403_forbidden(self):
        """Test that scan_image does NOT retry on 403 forbidden errors."""
        image_path = self.create_temp_image()
        try:
            attempt_count = 0

            def mock_generate_content(*args, **kwargs):
                nonlocal attempt_count
                attempt_count += 1
                raise _create_client_error(403, "Access denied")

            with patch('meals.services.vision_service.genai.Client') as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.models.generate_content = mock_generate_content

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

            def mock_generate_content(*args, **kwargs):
                nonlocal attempt_count
                attempt_count += 1
                raise _create_client_error(413, "Request entity too large")

            with patch('meals.services.vision_service.genai.Client') as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.models.generate_content = mock_generate_content

                with pytest.raises(ValueError) as exc_info:
                    scan_image(image_path)

                assert "too large" in str(exc_info.value).lower()
                assert attempt_count == 1  # No retry

        finally:
            if os.path.exists(image_path):
                os.remove(image_path)

    def test_scan_image_retries_on_timeout_error(self):
        """Test that scan_image retries on httpx timeout errors (the regression test)."""
        image_path = self.create_temp_image()
        try:
            attempt_count = 0

            def mock_generate_content(*args, **kwargs):
                nonlocal attempt_count
                attempt_count += 1
                if attempt_count <= 2:
                    # Fail first 2 attempts with real timeout error
                    raise httpx.TimeoutException("Request timed out")
                # Succeed on 3rd attempt
                response = MagicMock()
                response.text = "a sandwich with fries"
                return response

            with patch('meals.services.vision_service.genai.Client') as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.models.generate_content = mock_generate_content

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
            def mock_generate_content(*args, **kwargs):
                raise httpx.TimeoutException("Request timed out")

            with patch('meals.services.vision_service.genai.Client') as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.models.generate_content = mock_generate_content

                with pytest.raises(LLMServiceError) as exc_info:
                    scan_image(image_path)

                # Should be LLMServiceError (503), not ValueError (422)
                assert "timed out" in str(exc_info.value).lower()

        finally:
            if os.path.exists(image_path):
                os.remove(image_path)

    def test_scan_image_retries_on_connect_error(self):
        """Test that scan_image retries on httpx connect errors."""
        image_path = self.create_temp_image()
        try:
            attempt_count = 0

            def mock_generate_content(*args, **kwargs):
                nonlocal attempt_count
                attempt_count += 1
                if attempt_count == 1:
                    # Fail once with connection error
                    raise httpx.ConnectError("Connection refused")
                # Succeed on 2nd attempt
                response = MagicMock()
                response.text = "a salad"
                return response

            with patch('meals.services.vision_service.genai.Client') as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.models.generate_content = mock_generate_content

                result = scan_image(image_path)
                assert result == "a salad"
                assert attempt_count == 2  # Retried once

        finally:
            if os.path.exists(image_path):
                os.remove(image_path)

    def test_scan_image_retries_on_429_with_size_message(self):
        """Test that scan_image retries on 429 errors even if message mentions size.

        This is a regression test for a bug where status-code-based dispatch
        was incorrectly overridden by message text matching.
        """
        image_path = self.create_temp_image()
        try:
            attempt_count = 0

            def mock_generate_content(*args, **kwargs):
                nonlocal attempt_count
                attempt_count += 1
                if attempt_count <= 2:
                    # Fail first 2 attempts with 429 error containing "too large"
                    raise _create_client_error(429, "Request too large for quota")
                # Succeed on 3rd attempt
                response = MagicMock()
                response.text = "eggs with toast"
                return response

            with patch('meals.services.vision_service.genai.Client') as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.models.generate_content = mock_generate_content

                result = scan_image(image_path)
                assert result == "eggs with toast"
                # Should retry (2 failures, then success on 3rd) — NOT abort immediately
                assert attempt_count == 3

        finally:
            if os.path.exists(image_path):
                os.remove(image_path)

    def test_scan_image_429_exhausted_raises_llm_service_error(self):
        """Test that persistent 429 errors raise LLMServiceError (503), not ValueError (422)."""
        image_path = self.create_temp_image()
        try:
            def mock_generate_content(*args, **kwargs):
                raise _create_client_error(429, "Request too large for quota")

            with patch('meals.services.vision_service.genai.Client') as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.models.generate_content = mock_generate_content

                with pytest.raises(LLMServiceError) as exc_info:
                    scan_image(image_path)

                # Should be LLMServiceError (503), not ValueError (422)
                # Error message should indicate service is overloaded, not size issue
                assert "overloaded" in str(exc_info.value).lower()

        finally:
            if os.path.exists(image_path):
                os.remove(image_path)

    def test_scan_image_max_tokens_passed_to_gemini(self):
        """Test that max_tokens setting is passed through GenerateContentConfig."""
        image_path = self.create_temp_image()
        try:
            call_kwargs = {}

            def mock_generate_content(*args, **kwargs):
                nonlocal call_kwargs
                call_kwargs = kwargs
                response = MagicMock()
                response.text = "test food"
                return response

            with patch('meals.services.vision_service.genai.Client') as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.models.generate_content = mock_generate_content

                scan_image(image_path)

                # Verify GenerateContentConfig was passed with max_output_tokens
                assert "config" in call_kwargs
                config = call_kwargs["config"]
                # Default should be 600 (from settings)
                assert config.max_output_tokens == 600

        finally:
            if os.path.exists(image_path):
                os.remove(image_path)

    def test_scan_image_empty_response_raises_value_error(self):
        """Test that empty response from Gemini raises ValueError."""
        image_path = self.create_temp_image()
        try:
            def mock_generate_content(*args, **kwargs):
                response = MagicMock()
                response.text = ""  # Empty response
                return response

            with patch('meals.services.vision_service.genai.Client') as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.models.generate_content = mock_generate_content

                with pytest.raises(ValueError) as exc_info:
                    scan_image(image_path)

                assert "could not extract" in str(exc_info.value).lower()

        finally:
            if os.path.exists(image_path):
                os.remove(image_path)
