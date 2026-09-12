import logging
from .llm_service import parse_meal, LLMServiceError

logger = logging.getLogger(__name__)

DIVERGENCE_THRESHOLD = 0.20  # 20% — trigger refinement if LLM vs DB estimates diverge beyond this


def items_diverge(llm_item: dict, db_item: dict, threshold: float = DIVERGENCE_THRESHOLD) -> bool:
	"""
	Check if two macro estimates (LLM and DB-matched) diverge beyond a threshold.
	Compares calories, protein_g, carbs_g, fats_g as relative percent differences.
	Returns True if any field exceeds the threshold, False otherwise.
	"""
	epsilon = 1.0  # Avoid division by zero on very small values
	fields = ["calories", "protein_g", "carbs_g", "fats_g"]

	for field in fields:
		llm_val = llm_item.get(field, 0)
		db_val = db_item.get(field, 0)

		if db_val > 0:
			diff_pct = abs(llm_val - db_val) / max(db_val, epsilon)
			if diff_pct > threshold:
				logger.debug(
					f"Divergence on {field}: LLM={llm_val}, DB={db_val}, diff={diff_pct:.1%}"
				)
				return True

	return False


def validate_macros(meal_items: list[dict]) -> dict:
    """
    Validate calorie calculations against macros.
    Formula: expected_calories = (protein_g * 4) + (carbs_g * 4) + (fats_g * 9)
    Allow ±10% tolerance; correct to nearest 5 kcal if off.

    Returns:
        {"valid": bool, "warnings": [...], "corrected_items": [...]}
    """
    warnings = []
    corrected_items = []

    for item in meal_items:
        corrected = item.copy()
        protein_g = item.get("protein_g", 0)
        carbs_g = item.get("carbs_g", 0)
        fats_g = item.get("fats_g", 0)
        reported_calories = item.get("calories", 0)

        expected_calories = (protein_g * 4) + (carbs_g * 4) + (fats_g * 9)

        if expected_calories > 0:
            diff_pct = abs(reported_calories - expected_calories) / expected_calories
            if diff_pct > 0.10:
                warning = (
                    f"{item.get('item_name', 'Unknown')}: "
                    f"calories {reported_calories} seem off for macros "
                    f"(expected ~{expected_calories:.0f}); correcting to {round(expected_calories / 5) * 5}"
                )
                warnings.append(warning)
                logger.warning("Macro validation: %s", warning)
                corrected["calories"] = round(expected_calories / 5) * 5

        corrected_items.append(corrected)

    return {
        "valid": len(warnings) == 0,
        "warnings": warnings,
        "corrected_items": corrected_items,
    }


def get_nutrition_estimate(food_name: str, quantity: float, unit: str) -> dict:
    """Get nutrition estimate for a food item via LLM."""
    prompt = f"""Provide nutrition information for this food item. Return JSON only, no explanation.
Food: {quantity}{unit} of {food_name}

Return this exact JSON format:
{{
  "calories": <integer>,
  "protein_g": <float>,
  "carbs_g": <float>,
  "fats_g": <float>,
  "fiber_g": <float>
}}"""

    try:
        result = parse_meal(prompt)
        if result and len(result) > 0:
            item = result[0]
            return {
                "calories": item.get("calories", 0),
                "protein_g": item.get("protein_g", 0),
                "carbs_g": item.get("carbs_g", 0),
                "fats_g": item.get("fats_g", 0),
                "fiber_g": item.get("fiber_g", 0),
            }
    except (LLMServiceError, Exception) as e:
        logger.warning("Failed to get nutrition for %s: %s", food_name, e)

    return {
        "calories": 0,
        "protein_g": 0,
        "carbs_g": 0,
        "fats_g": 0,
        "fiber_g": 0,
    }
