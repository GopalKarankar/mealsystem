import json
import logging
import re
from groq import Groq, GroqError
from django.conf import settings

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Raised when the Groq LLM call itself could not be completed or trusted."""
    pass


SYSTEM_PROMPT = """You are a nutrition data extraction assistant. Given a transcript of a person
describing what they ate, extract each distinct food/drink item and estimate its nutrition.

Return ONLY a valid JSON array, no markdown code fences, no explanation, no surrounding text.
Each element must be an object with exactly these fields:
item_name (string), quantity (number > 0), unit (string), serving_size_grams (number or null),
calories (number >= 0), protein_g (number >= 0), carbs_g (number >= 0), fats_g (number >= 0),
fiber_g (number >= 0, default 0 if unknown), confidence (number 0-1).

If the transcript does not clearly describe any food or drink, return: []

Use standard nutrition knowledge for typical serving sizes when the speaker is vague.
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
        client = Groq(api_key=settings.GROQ_API_KEY)

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
