import base64
import logging
import mimetypes
import time
import httpx
from google import genai
from google.genai import errors, types
from django.conf import settings
from meals.services.llm_service import LLMServiceError

logger = logging.getLogger(__name__)

VISION_PROMPT = (
    "Describe this image for a nutrition-tracking app. If it shows food or a meal, "
    "list each distinct food/drink item you can identify and any visible portion/quantity cues. "
    "If it shows a nutrition facts label, receipt, or menu, transcribe the relevant food names, "
    "quantities, and any calorie/macro numbers exactly as printed. Be concise and factual; "
    "do not guess at things you cannot see."
)


def scan_image(image_path: str) -> str:
    """Describe an uploaded image via Google Gemini vision model.

    Args:
        image_path: Path to a JPEG/PNG/WEBP file already validated at the API boundary.

    Returns:
        A text description suitable for feeding into llm_service.parse_meal().

    Raises:
        ValueError: friendly message for auth/timeout/unsupported-format/size failures.
        LLMServiceError: service capacity/rate-limit failures (will return 503 to client).
    """
    mime_type, _ = mimetypes.guess_type(image_path)
    mime_type = mime_type or "image/jpeg"
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    max_retries = 2
    backoff_delays = [0.5, 1.5]

    for attempt in range(max_retries + 1):
        try:
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            response = client.models.generate_content(
                model=settings.GEMINI_VISION_MODEL,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    VISION_PROMPT,
                ],
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=settings.LLM_VISION_MAX_TOKENS,
                ),
            )
            description = response.text.strip()
            if not description:
                raise ValueError("Could not extract any description from the photo. Please try a clearer photo.")
            return description

        except errors.ClientError as e:
            status_code = e.code
            error_msg = e.message or str(e)

            if status_code in (401, 403):
                logger.error("Gemini vision API authentication error (status %d): %s", status_code, error_msg)
                raise ValueError("Vision service authentication failed")

            if status_code == 429:
                if attempt < max_retries:
                    delay = backoff_delays[attempt]
                    logger.warning("Gemini vision API rate limit (attempt %d/%d), retrying in %.1fs: %s",
                                   attempt + 1, max_retries + 1, delay, error_msg)
                    time.sleep(delay)
                    continue
                else:
                    logger.error("Gemini vision API rate limit after %d retries: %s", max_retries + 1, error_msg)
                    raise LLMServiceError("Vision service is currently overloaded; please try again shortly")

            if status_code in (400, 413) and ("size" in error_msg.lower() or "large" in error_msg.lower()):
                logger.error("Gemini vision API error (status %d): %s", status_code, error_msg)
                raise ValueError("Photo is too large for the vision service")

            logger.error("Gemini vision API error (status %d): %s", status_code, error_msg)
            raise ValueError(f"Photo scanning failed: {error_msg}")

        except errors.ServerError as e:
            error_msg = e.message or str(e)

            if attempt < max_retries:
                delay = backoff_delays[attempt]
                logger.warning("Gemini vision API server error (attempt %d/%d), retrying in %.1fs: %s",
                               attempt + 1, max_retries + 1, delay, error_msg)
                time.sleep(delay)
                continue
            else:
                logger.error("Gemini vision API server error after %d retries: %s", max_retries + 1, error_msg)
                raise LLMServiceError("Vision service is currently overloaded; please try again shortly")

        except (httpx.TimeoutException, httpx.ConnectError) as e:
            error_msg = str(e)

            if attempt < max_retries:
                delay = backoff_delays[attempt]
                logger.warning("Gemini vision API timeout/connection error (attempt %d/%d), retrying in %.1fs: %s",
                               attempt + 1, max_retries + 1, delay, error_msg)
                time.sleep(delay)
                continue
            else:
                logger.error("Gemini vision API timed out after %d retries: %s", max_retries + 1, error_msg)
                raise LLMServiceError("Vision service timed out; please try again shortly")

        except errors.APIError as e:
            error_msg = e.message or str(e)
            logger.error("Gemini vision API error: %s", error_msg)
            raise ValueError(f"Photo scanning failed: {error_msg}")

        except ValueError:
            raise
        except Exception as e:
            logger.error("Unexpected error in vision service: %s", e)
            raise ValueError(f"Photo scanning failed: {e}")
