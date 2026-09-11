import json
import logging
import mimetypes
import time
import httpx
from typing import Optional
from pydantic import BaseModel, Field
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

STRUCTURED_VISION_PROMPT = """You are a professional food recognition and nutrition estimation system. Your task is to analyze food images and return structured, machine-readable JSON data.

## Instructions

1. **Image Analysis** - Identify all visible food items, estimate portions, detect text/labels
2. **Confidence Scoring** - Score 0.0-1.0: 0.85+ easily identifiable, 0.65-0.85 some ambiguity, <0.65 unclear
3. **Portion Estimation** - Use g, ml, pieces, cups, tbsp; provide single best estimate
4. **Visual Evidence** - Brief description of what led to identification
5. **Output Format** - Return ONLY valid JSON

Return JSON only:
{
  "foods": [
    {
      "name": "food name (lowercase)",
      "estimated_quantity": 100,
      "unit": "g|ml|piece|cup|tbsp",
      "confidence": 0.85,
      "visual_evidence": "short description"
    }
  ],
  "overall_confidence": 0.83,
  "ambiguities": [],
  "text_found": null
}

6. **Edge Cases** - Empty image: {"foods": [], "overall_confidence": 0.0}
7. **Food Names** - Common names, not scientific. Include prep hints if ambiguous.

## Important Constraints
- NO explanations or preamble. Return JSON only.
- NO markdown formatting.
- Quantities must be integers or floats.
- No null/undefined foods."""


class FoodItem(BaseModel):
    """Structured food item from vision analysis."""
    name: str
    estimated_quantity: float
    unit: str
    confidence: float = Field(ge=0.0, le=1.0)
    visual_evidence: str


class VisionResponse(BaseModel):
    """Structured response from Gemini vision analysis."""
    foods: list[FoodItem] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0.0, le=1.0)
    ambiguities: Optional[list[str]] = Field(default_factory=list)
    text_found: Optional[str] = None


def scan_image(image_path: str) -> str:
    """Describe an uploaded image via Google Gemini vision model."""
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


def analyze_food_image(image_path: str) -> VisionResponse:
    """Analyze a food image and return structured food data."""
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
                    STRUCTURED_VISION_PROMPT,
                ],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=600,
                ),
            )
            raw_text = response.text.strip()
            if not raw_text:
                raise ValueError("Could not extract any data from the photo. Please try a clearer photo.")

            # Remove markdown code blocks if present (safety)
            if raw_text.startswith("`"):
                raw_text = raw_text.split("`")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]

            # Parse and validate JSON
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError as e:
                logger.error("Gemini returned invalid JSON: %s", raw_text[:200])
                raise ValueError("Vision model returned malformed response. Please try again.")

            # Validate with Pydantic
            try:
                result = VisionResponse(**data)
            except ValueError as e:
                logger.error("Vision response validation failed: %s", e)
                raise ValueError("Vision response does not match expected format. Please try again.")

            if not result.foods:
                raise ValueError("No food items could be identified in the photo. Please try a clearer photo of the food, label, or menu.")

            logger.info(f"Food recognition successful. Found {len(result.foods)} items, confidence: {result.overall_confidence}")
            return result

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
