import json
import logging
import re
import string
from pathlib import Path

import requests
from django.conf import settings

from .units import ALLOWED_UNITS, get_gram_equivalent, normalize_unit

logger = logging.getLogger(__name__)

_IFCT_FOODS = None


def _load_ifct_foods():
    global _IFCT_FOODS
    if _IFCT_FOODS is None:
        ifct_path = Path(__file__).parent.parent / "data" / "ifct_foods.json"
        with open(ifct_path, "r") as f:
            _IFCT_FOODS = json.load(f)
    return _IFCT_FOODS


def _normalize_name(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(f"[{re.escape(string.punctuation)}]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name


def lookup_ifct(item_name: str) -> dict | None:
    """
    Look up a food item in IFCT (bundled curated dataset).
    Returns per-100g nutrition data + metadata, or None if not found.

    Args:
        item_name: e.g., "rice", "daal", "roti"

    Returns:
        {
            "item_name": "...",
            "calories_per_100g": 130.0,
            "protein_g_per_100g": 2.7,
            "carbs_g_per_100g": 28.0,
            "fats_g_per_100g": 0.3,
            "fiber_g_per_100g": 0.4,
            "aliases": ["basmati", "white rice"],
            "source": "ifct",
            "source_detail": "IFCT 2017, NIN (Longvah et al.)"
        }
        or None
    """
    try:
        foods = _load_ifct_foods()
        normalized_input = _normalize_name(item_name)

        for food in foods:
            if _normalize_name(food["item_name"]) == normalized_input:
                return {
                    "item_name": food["item_name"],
                    "calories_per_100g": food["calories_per_100g"],
                    "protein_g_per_100g": food["protein_g_per_100g"],
                    "carbs_g_per_100g": food["carbs_g_per_100g"],
                    "fats_g_per_100g": food["fats_g_per_100g"],
                    "fiber_g_per_100g": food["fiber_g_per_100g"],
                    "aliases": food.get("aliases", []),
                    "source": "ifct",
                    "source_detail": food.get("source_detail", "IFCT"),
                }

            for alias in food.get("aliases", []):
                if _normalize_name(alias) == normalized_input:
                    return {
                        "item_name": food["item_name"],
                        "calories_per_100g": food["calories_per_100g"],
                        "protein_g_per_100g": food["protein_g_per_100g"],
                        "carbs_g_per_100g": food["carbs_g_per_100g"],
                        "fats_g_per_100g": food["fats_g_per_100g"],
                        "fiber_g_per_100g": food["fiber_g_per_100g"],
                        "aliases": food.get("aliases", []),
                        "source": "ifct",
                        "source_detail": food.get("source_detail", "IFCT"),
                    }

        logger.debug("IFCT lookup for '%s' returned no match", item_name)
        return None

    except Exception as e:
        logger.warning("IFCT lookup error for '%s': %s", item_name, str(e))
        return None


def lookup_usda(item_name: str) -> dict | None:
    """
    Look up a food item in USDA FoodData Central.
    Returns per-100g nutrition data for the first result, or None if API fails/no match.

    Args:
        item_name: e.g., "banana", "chicken breast"

    Returns:
        {
            "item_name": "...",
            "calories_per_100g": 89.0,
            "protein_g_per_100g": 1.09,
            "carbs_g_per_100g": 23.0,
            "fats_g_per_100g": 0.33,
            "fiber_g_per_100g": 2.6,
            "fdc_id": "168101",
            "source": "usda_fdc",
            "source_detail": "FDC v1, Foundation/SR Legacy"
        }
        or None
    """
    if not settings.USDA_API_KEY:
        logger.debug("USDA_API_KEY not configured, skipping USDA lookup for '%s'", item_name)
        return None

    try:
        url = f"{settings.USDA_API_BASE_URL}/foods/search"
        params = {
            "query": item_name,
            "api_key": settings.USDA_API_KEY,
            "pageSize": 1,
            "dataType": ["Foundation", "SR Legacy"],
        }

        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()

        data = response.json()
        foods = data.get("foods", [])

        if not foods:
            logger.debug("USDA lookup for '%s' returned no results", item_name)
            return None

        food = foods[0]
        fdc_id = food.get("fdcId")
        description = food.get("description", item_name)
        nutrients = food.get("foodNutrients", [])

        nutrient_map = {}
        for nutrient in nutrients:
            nutrient_id = nutrient.get("nutrientId")
            value = nutrient.get("value", 0)
            if nutrient_id in [1003, 1004, 1005, 1008, 1079]:
                nutrient_map[nutrient_id] = value

        calories_per_100g = nutrient_map.get(1008, 0)
        protein_g_per_100g = nutrient_map.get(1003, 0)
        carbs_g_per_100g = nutrient_map.get(1005, 0)
        fats_g_per_100g = nutrient_map.get(1004, 0)
        fiber_g_per_100g = nutrient_map.get(1079, 0)

        return {
            "item_name": description,
            "calories_per_100g": calories_per_100g,
            "protein_g_per_100g": protein_g_per_100g,
            "carbs_g_per_100g": carbs_g_per_100g,
            "fats_g_per_100g": fats_g_per_100g,
            "fiber_g_per_100g": fiber_g_per_100g,
            "fdc_id": str(fdc_id) if fdc_id else None,
            "source": "usda_fdc",
            "source_detail": "FDC v1, Foundation/SR Legacy",
        }

    except requests.RequestException as e:
        logger.warning("USDA API error for '%s': %s", item_name, str(e))
        return None
    except (ValueError, KeyError, IndexError) as e:
        logger.warning("USDA response parsing error for '%s': %s", item_name, str(e))
        return None
    except Exception as e:
        logger.warning("Unexpected error during USDA lookup for '%s': %s", item_name, str(e))
        return None


def resolve_item_macros(item: dict) -> dict:
    """
    Resolve food item nutrition by priority: IFCT → USDA → LLM estimate.
    On match, override item's calories/macros and set source appropriately.

    Args:
        item: from MealItemCreateSerializer (has item_name, serving_size_grams,
              quantity, unit, calories, protein_g, etc., and optional source)

    Returns:
        item (dict) with potentially overridden macros and updated source
    """
    item_name = item.get("item_name", "")
    if not item_name:
        return item

    match = lookup_ifct(item_name)
    if not match:
        match = lookup_usda(item_name)

    if not match:
        return item

    serving_size_grams = item.get("serving_size_grams")
    scale_factor = None

    if serving_size_grams is not None and serving_size_grams > 0:
        scale_factor = serving_size_grams / 100.0
    else:
        unit = str(item.get("unit", "")).lower()
        quantity = item.get("quantity", 0)

        grams_per_unit = get_gram_equivalent(unit)
        if quantity > 0 and grams_per_unit:
            scale_factor = (quantity * grams_per_unit) / 100.0

    if scale_factor is None:
        logger.warning(
            "Cannot scale %s: unknown serving size and non-weight unit %s",
            item_name,
            item.get("unit", "unknown"),
        )
        return item

    item["calories"] = match["calories_per_100g"] * scale_factor
    item["protein_g"] = match["protein_g_per_100g"] * scale_factor
    item["carbs_g"] = match["carbs_g_per_100g"] * scale_factor
    item["fats_g"] = match["fats_g_per_100g"] * scale_factor
    item["fiber_g"] = match["fiber_g_per_100g"] * scale_factor

    item["confidence"] = max(item.get("confidence", 0.85), 0.90)
    item["source"] = match["source"]

    return item




def needs_fresh_lookup(old_name: str, new_name: str, threshold: float = 0.85) -> bool:
    """String-similarity heuristic: does an item-name edit warrant a fresh IFCT/USDA lookup
    (different food) rather than a proportional macro rescale (same food, qty/unit tweak)?"""
    from difflib import SequenceMatcher
    ratio = SequenceMatcher(None, old_name.lower().strip(), new_name.lower().strip()).ratio()
    return ratio < threshold


def rescale_item_macros(base_macros: dict, *, old_quantity: float, old_unit: str,
                         new_quantity: float, new_unit: str) -> dict | None:
    """Proportionally scale base_macros (server-authoritative, e.g. a stored MealItem's values)
    from (old_quantity, old_unit) to (new_quantity, new_unit). Same-unit edits (including
    count-based units like piece/serving) scale by quantity ratio directly. A unit change
    requires both units to have a known gram equivalent. Returns None if the scale can't be
    determined — caller must fall back to a fresh lookup."""
    old_unit = str(old_unit).lower()
    new_unit = str(new_unit).lower()
    if old_quantity <= 0:
        return None

    if old_unit == new_unit:
        scale = new_quantity / old_quantity
    else:
        old_grams = get_gram_equivalent(old_unit)
        new_grams = get_gram_equivalent(new_unit)
        if not old_grams or not new_grams:
            return None
        scale = (new_quantity * new_grams) / (old_quantity * old_grams)

    return {k: base_macros.get(k, 0) * scale for k in
            ("calories", "protein_g", "carbs_g", "fats_g", "fiber_g")}
