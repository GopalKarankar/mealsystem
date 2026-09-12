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

REFINEMENT_PROMPT = """You are a nutrition data reconciliation assistant. You are given two independent nutrition
estimates for a single food item:
1. An LLM-generated estimate (possibly vague or off due to transcription/context loss)
2. A matched database record from IFCT (Indian Food Composition Tables) or USDA FoodData Central

Your task: Return the most plausible final nutrition values, reconciling or blending the two estimates
as appropriate given the food name, quantity, and unit context. You are the final judge — pick the
best values for this specific serving.

Return ONLY a valid JSON object, no markdown, no explanation, no surrounding text.
Fields must be: calories (number >= 0), protein_g (number >= 0), carbs_g (number >= 0),
fats_g (number >= 0), fiber_g (number >= 0), confidence (number 0-1).

All values must be valid numbers (not null, not strings) and confidence must be 0 <= confidence <= 1.
If you cannot reconcile (contradictory info), pick the more reliable source (prefer DB match over vague LLM)."""


def refine_meal_item(
	item_name: str,
	quantity: float,
	unit: str,
	llm_estimate: dict,
	db_match: dict,
	db_source: str,
) -> dict:
	"""
	Reconcile LLM estimate vs. DB-matched nutrition via Groq LLM.
	Returns refined macro dict (calories, protein_g, carbs_g, fats_g, fiber_g, confidence)
	with schema validation. Raises LLMServiceError on any API/validation failure.

	Args:
		item_name: Food item name (for context)
		quantity: Quantity value
		unit: Unit (piece, g, ml, etc.)
		llm_estimate: Dict with calories, protein_g, carbs_g, fats_g, fiber_g
		db_match: Dict with calories, protein_g, carbs_g, fats_g, fiber_g
		db_source: "ifct" or "usda_fdc" (for context in the prompt)

	Returns:
		Dict with refined macros and confidence

	Raises:
		LLMServiceError: If Groq API fails, returns invalid JSON, or validation fails
	"""
	user_prompt = f"""Food: {quantity} {unit} of {item_name}
Database match source: {db_source}

LLM estimate:
{{
  "calories": {llm_estimate.get('calories', 0)},
  "protein_g": {llm_estimate.get('protein_g', 0)},
  "carbs_g": {llm_estimate.get('carbs_g', 0)},
  "fats_g": {llm_estimate.get('fats_g', 0)},
  "fiber_g": {llm_estimate.get('fiber_g', 0)}
}}

Database match ({db_source}):
{{
  "calories": {db_match.get('calories', 0)},
  "protein_g": {db_match.get('protein_g', 0)},
  "carbs_g": {db_match.get('carbs_g', 0)},
  "fats_g": {db_match.get('fats_g', 0)},
  "fiber_g": {db_match.get('fiber_g', 0)}
}}

Return your best reconciled estimate as JSON only."""

	try:
		client = Groq(api_key=settings.GROQ_API_KEY, timeout=20.0, max_retries=0)

		response = client.chat.completions.create(
			model=settings.LLM_MODEL,
			messages=[
				{"role": "system", "content": REFINEMENT_PROMPT},
				{"role": "user", "content": user_prompt},
			],
			temperature=0.3,  # Lower temp for reconciliation (more deterministic)
			top_p=0.9,
		)

		content = response.choices[0].message.content.strip()

		# Strip markdown fences (same as parse_meal)
		content = re.sub(r'^```(?:json)?\n?', '', content)
		content = re.sub(r'\n?```$', '', content)
		content = content.strip()

		try:
			refined = json.loads(content)
			if not isinstance(refined, dict):
				raise ValueError("Response is not a JSON object")
		except json.JSONDecodeError as e:
			logger.error("Failed to parse refinement JSON from LLM: %s", e)
			raise LLMServiceError(f"Refinement LLM returned invalid JSON: {e}")

		# Schema and range validation (untrusted model output)
		required_fields = ["calories", "protein_g", "carbs_g", "fats_g", "fiber_g", "confidence"]
		for field in required_fields:
			if field not in refined:
				raise LLMServiceError(f"Refinement response missing required field: {field}")
			val = refined[field]
			if not isinstance(val, (int, float)):
				raise LLMServiceError(f"Field {field} is not numeric: {val}")
			if val < 0:
				raise LLMServiceError(f"Field {field} is negative: {val}")

		# Confidence must be in [0, 1]
		if not (0 <= refined["confidence"] <= 1):
			raise LLMServiceError(f"Confidence out of range [0,1]: {refined['confidence']}")

		return refined

	except GroqError as e:
		logger.error("Groq API error during refinement: %s", e)
		raise LLMServiceError(f"Refinement LLM service error: {e}")
	except LLMServiceError:
		raise  # Re-raise validation errors as-is
	except Exception as e:
		logger.error("Unexpected error in refinement service: %s", e)
		raise LLMServiceError(f"Unexpected refinement error: {e}")


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
