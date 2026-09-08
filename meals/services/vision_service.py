import base64
import logging
import mimetypes
from groq import Groq, GroqError
from django.conf import settings

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
    """
    try:
        mime_type, _ = mimetypes.guess_type(image_path)
        mime_type = mime_type or "image/jpeg"
        with open(image_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
        data_uri = f"data:{mime_type};base64,{b64_data}"

        client = Groq(api_key=settings.GROQ_API_KEY)
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
        )
        description = response.choices[0].message.content.strip()
        if not description:
            raise ValueError("Could not extract any description from the photo. Please try a clearer photo.")
        return description

    except GroqError as e:
        error_msg = str(e)
        logger.error("Groq vision API error: %s", error_msg)
        if "401" in error_msg or "authentication" in error_msg.lower():
            raise ValueError("Vision service authentication failed")
        elif "timeout" in error_msg.lower():
            raise ValueError("Photo scanning timed out; please try again")
        elif "413" in error_msg or "too large" in error_msg.lower():
            raise ValueError("Photo is too large for the vision service")
        else:
            raise ValueError(f"Photo scanning failed: {error_msg}")
    except ValueError:
        raise
    except Exception as e:
        logger.error("Unexpected error in vision service: %s", e)
        raise ValueError(f"Photo scanning failed: {e}")
