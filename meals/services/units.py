"""Unit definitions and utilities for nutrition data."""

ALLOWED_UNITS = {
    "g": 1.0, "kg": 1000.0, "ml": 1.0, "l": 1000.0, "oz": 28.3495,
    "cup": 240.0, "bowl": 400.0, "plate": 300.0,
    "piece": None, "serving": None,
}


def get_gram_equivalent(unit: str) -> float | None:
    """Approximate grams for one unit, or None if unconvertible (piece/serving)."""
    return ALLOWED_UNITS.get(str(unit).lower())


UNIT_SYNONYMS = {
    "gram": "g", "grams": "g",
    "ounce": "oz", "ounces": "oz",
    "milliliter": "ml", "milliliters": "ml", "millilitre": "ml", "millilitres": "ml",
    "liter": "l", "liters": "l", "litre": "l", "litres": "l",
}


def normalize_unit(unit: str) -> str:
    """Best-effort map an LLM-provided unit string onto ALLOWED_UNITS.
    Returns the input lowercased/stripped unchanged if no safe mapping exists;
    callers must still validate the result against ALLOWED_UNITS."""
    if not unit:
        return unit
    u = str(unit).strip().lower()
    if u in ALLOWED_UNITS:
        return u
    if u in UNIT_SYNONYMS:
        return UNIT_SYNONYMS[u]
    if u.endswith("s"):
        singular = u[:-1]
        if singular in ALLOWED_UNITS:
            return singular
        if singular in UNIT_SYNONYMS:
            return UNIT_SYNONYMS[singular]
    return u
