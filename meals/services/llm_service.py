import json
import logging
import re
from groq import Groq, GroqError
from django.conf import settings

from .units import ALLOWED_UNITS

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Raised when the Groq LLM call itself could not be completed or trusted."""
    pass


_ALLOWED_UNITS_STR = ", ".join(sorted(ALLOWED_UNITS.keys()))

SYSTEM_PROMPT = f"""You are a nutrition data extraction assistant. Given a transcript of a person
describing what they ate, extract each distinct food/drink item and estimate its nutrition.

Return ONLY a valid JSON array, no markdown code fences, no explanation, no surrounding text.
Each element must be an object with exactly these fields:
item_name (string), quantity (number > 0), unit (string), serving_size_grams (number or null),
calories (number >= 0), protein_g (number >= 0), carbs_g (number >= 0), fats_g (number >= 0),
fiber_g (number >= 0, default 0 if unknown), confidence (number 0-1).

UNIT RULES (strict):
- "unit" MUST be exactly one of these {len(ALLOWED_UNITS)} lowercase strings: {_ALLOWED_UNITS_STR}.
- Never use a plural form (e.g. "pieces", "servings", "grams") or any other word. Always singular,
  always from the list above.
- Use "piece" for discrete, countable food items: fruits (banana, apple, egg), individual items
  (roti, idli, samosa), or slices/units treated as one countable thing.
- Use "serving" as the fallback when no other unit fits or the speaker describes a generic portion
  ("a serving of rice", "some dal") and you cannot map it to a more specific unit.
- Use "g" / "kg" for solids described by weight, "ml" / "l" for liquids described by volume,
  "oz" for items given in ounces, and "cup" / "bowl" / "plate" for container-based portions
  (e.g. "a bowl of curd", "a plate of rice").

QUANTITY RULES:
- If the speaker states an explicit count or amount, use it exactly (e.g. "4 bananas" -> quantity: 4;
  "200g of rice" -> quantity: 200, unit: "g").
- If no count is stated, estimate a sensible default (e.g. "banana" (no count) -> quantity: 1,
  unit: "piece"; "rice" (no count) -> quantity: 1, unit: "serving").
- Use standard nutrition knowledge for typical serving sizes when the speaker is vague.

EXAMPLES:
Input: "i ate 4 bananas"
Output: [{{"item_name": "banana", "quantity": 4, "unit": "piece", "serving_size_grams": 118, "calories": 421, "protein_g": 5.2, "carbs_g": 108.8, "fats_g": 1.6, "fiber_g": 12.4, "confidence": 0.9}}]

Input: "i had a bowl of curd and 200g rice"
Output: [{{"item_name": "curd", "quantity": 1, "unit": "bowl", "serving_size_grams": 400, "calories": 244, "protein_g": 14.0, "carbs_g": 18.8, "fats_g": 13.2, "fiber_g": 0, "confidence": 0.85}}, {{"item_name": "rice", "quantity": 200, "unit": "g", "serving_size_grams": 200, "calories": 260, "protein_g": 5.4, "carbs_g": 56.0, "fats_g": 0.6, "fiber_g": 0.8, "confidence": 0.9}}]

If the transcript does not clearly describe any food or drink, return: []

Do not invent items that were not mentioned."""


def parse_meal(transcript: str) -> list[dict]:
    """
    Parse meal transcript into structured JSON using Groq LLM.

    Args:
        transcript: Text from Whisper transcription

    Returns:
        List of meal items as dicts (empty only if model legitimately returns empty for food-less transcript)

    Raises:
        LLMServiceError: If the Groq API call fails (auth, rate limit, network, etc.)
    """
    if not transcript or not transcript.strip():
        return []

    try:
        client = Groq(api_key=settings.GROQ_API_KEY, timeout=20.0, max_retries=0)

        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ],
            temperature=0.7,
            top_p=0.9,
        )

        content = response.choices[0].message.content.strip()

        content = re.sub(r'^```(?:json)?\n?', '', content)
        content = re.sub(r'\n?```$', '', content)
        content = content.strip()

        if not content or content == "[]":
            return []

        try:
            items = json.loads(content)
            if not isinstance(items, list):
                raise ValueError("Response is not a JSON array")
            return items
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON from LLM: %s", e)
            raise LLMServiceError(f"LLM returned invalid JSON: {e}")

    except GroqError as e:
        logger.error("Groq API error: %s", e)
        raise LLMServiceError(f"LLM service error: {e}")
    except Exception as e:
        logger.error("Unexpected error in LLM service: %s", e)
        raise LLMServiceError(f"Unexpected error: {e}")
