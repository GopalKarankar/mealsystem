import base64
import logging
import mimetypes
import time
import groq
from groq import Groq, GroqError
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
    """Describe an uploaded image via a Groq vision-capable model.

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
        b64_data = base64.b64encode(f.read()).decode("utf-8")
    data_uri = f"data:{mime_type};base64,{b64_data}"

    max_retries = 2
    backoff_delays = [0.5, 1.5]

    for attempt in range(max_retries + 1):
        try:
            client = Groq(api_key=settings.GROQ_API_KEY, timeout=15.0, max_retries=0)
            response = client.chat.completions.create(
                model=settings.LLM_VISION_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }],
                temperature=0.3,
                max_tokens=settings.LLM_VISION_MAX_TOKENS,
            )
            description = response.choices[0].message.content.strip()
            if not description:
                raise ValueError("Could not extract any description from the photo. Please try a clearer photo.")
            return description

        except groq.AuthenticationError as e:
            logger.error("Groq vision API authentication error: %s", str(e))
            raise ValueError("Vision service authentication failed")

        except groq.APIStatusError as e:
            status_code = e.status_code
            error_msg = str(e)

            if status_code == 413:
                logger.error("Groq vision API error (status %d): %s", status_code, error_msg)
                raise ValueError("Photo is too large for the vision service")

            is_transient = status_code == 429 or status_code >= 500

            if is_transient and attempt < max_retries:
                delay = backoff_delays[attempt]
                logger.warning("Groq vision API transient error (status %d, attempt %d/%d), retrying in %.1fs: %s",
                               status_code, attempt + 1, max_retries + 1, delay, error_msg)
                time.sleep(delay)
                continue
            elif is_transient:
                logger.error("Groq vision API error after %d retries (status %d): %s", max_retries + 1, status_code, error_msg)
                raise LLMServiceError("Vision service is currently overloaded; please try again shortly")
            else:
                logger.error("Groq vision API error (status %d): %s", status_code, error_msg)
                raise ValueError(f"Photo scanning failed: {error_msg}")

        except groq.APIConnectionError as e:
            error_msg = str(e)

            if attempt < max_retries:
                delay = backoff_delays[attempt]
                logger.warning("Groq vision API timeout/connection error (attempt %d/%d), retrying in %.1fs: %s",
                               attempt + 1, max_retries + 1, delay, error_msg)
                time.sleep(delay)
                continue
            else:
                logger.error("Groq vision API timed out after %d retries: %s", max_retries + 1, error_msg)
                raise LLMServiceError("Vision service timed out; please try again shortly")

        except GroqError as e:
            error_msg = str(e)
            logger.error("Groq vision API error: %s", error_msg)
            raise ValueError(f"Photo scanning failed: {error_msg}")

        except ValueError:
            raise
        except Exception as e:
            logger.error("Unexpected error in vision service: %s", e)
            raise ValueError(f"Photo scanning failed: {e}")
