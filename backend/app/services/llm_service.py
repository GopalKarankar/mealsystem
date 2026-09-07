import json
import logging
import re
from groq import Groq, GroqError
from app.config import settings

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Raised when the Groq LLM call itself could not be completed or trusted
    (auth failure, rate limit, network/timeout, malformed API response) —
    as opposed to a successful call that legitimately found no food items."""
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
        client = Groq(api_key=settings.groq_api_key)

        response = client.chat.completions.create(
            model=settings.llm_model,
            max_tokens=2048,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Extract meal items from this transcript:\n\n{transcript}",
                }
            ],
        )

        result_text = _extract_text_from_response(response)
        items = _parse_json_array(result_text)

        if items is None:
            logger.warning(
                "Groq returned invalid JSON on first attempt for transcript: %s",
                transcript[:100],
            )
            items = _retry_with_clarification(client, result_text, transcript)

        if items is None:
            raise LLMServiceError(
                "Meal parsing service returned an unexpected response. Please try again in a moment."
            )

        return items

    except (GroqError, ValueError) as e:
        logger.exception("Groq LLM call failed")
        raise LLMServiceError(
            "Meal parsing service is temporarily unavailable. Please try again in a moment."
        ) from e


def _extract_text_from_response(response) -> str:
    return response.choices[0].message.content


def _parse_json_array(text: str) -> list[dict] | None:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    parsed = _try_json_loads(text)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict) and len(parsed) == 1:
        sole_value = next(iter(parsed.values()))
        if isinstance(sole_value, list):
            return sole_value

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        fallback = _try_json_loads(match.group(0))
        if isinstance(fallback, list):
            return fallback

    return None


def _try_json_loads(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _retry_with_clarification(client, invalid_text: str, transcript: str) -> list[dict] | None:
    response = client.chat.completions.create(
        model=settings.llm_model,
        max_tokens=2048,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Extract meal items from this transcript:\n\n{transcript}",
            },
            {
                "role": "assistant",
                "content": invalid_text,
            },
            {
                "role": "user",
                "content": "That was not valid JSON. Reply again with ONLY a valid JSON array.",
            },
        ],
    )

    result_text = _extract_text_from_response(response)
    return _parse_json_array(result_text)
