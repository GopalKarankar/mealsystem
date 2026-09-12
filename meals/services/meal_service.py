import logging
import os
from datetime import datetime, timedelta
from django.utils import timezone

from .whisper_service import transcribe
from .llm_service import parse_meal, LLMServiceError
from .nutrition_service import validate_macros
from .vision_service import scan_image
from .food_lookup_service import resolve_item_macros, needs_fresh_lookup, rescale_item_macros
from .units import normalize_unit
from ..models import Meal, MealItem

logger = logging.getLogger(__name__)

ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".webm"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def sniff_image_extension(file_obj) -> str | None:
    """Sniff actual image type from magic bytes, ignoring client-supplied name/MIME.

    Reads a small header, then rewinds the file object so callers can still
    stream its full contents afterward.
    """
    file_obj.seek(0)
    header = file_obj.read(16)
    file_obj.seek(0)

    # JPEG: FF D8 FF
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    # PNG: 89 50 4E 47 0D 0A 1A 0A
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    # WEBP: RIFF....WEBP
    if header[0:4] == b"RIFF" and header[8:12] == b"WEBP":
        return ".webp"
    return None


def derive_meal_category_from_time(dt) -> str:
    """Auto-derive a meal category from a datetime's local hour."""
    hour = timezone.localtime(dt).hour
    if 5 <= hour < 7:
        return 'early_morning'
    elif 7 <= hour < 10:
        return 'breakfast'
    elif 10 <= hour < 12:
        return 'mid_morning'
    elif 12 <= hour < 14:
        return 'lunch'
    elif 14 <= hour < 17:
        return 'afternoon_snack'
    elif 17 <= hour < 21:
        return 'dinner'
    else:
        return 'bedtime'


def get_confidence_badge(score: float) -> str:
    """Return a confidence badge color based on the score."""
    if score > 0.90:
        return "green"
    elif score >= 0.70:
        return "orange"
    else:
        return "red"


def calculate_daily_totals(meals: list) -> dict:
    """Calculate daily totals from a list of Meal objects."""
    totals = {
        "calories": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fats_g": 0.0,
        "fiber_g": 0.0,
    }
    for meal in meals:
        for item in meal.meal_items.all():
            totals["calories"] += item.calories
            totals["protein_g"] += item.protein_g
            totals["carbs_g"] += item.carbs_g
            totals["fats_g"] += item.fats_g
            totals["fiber_g"] += item.fiber_g
    return totals


def calculate_confidence_distribution(meals: list) -> dict:
    """Calculate confidence distribution from a list of Meal objects."""
    if not meals:
        return {"high": 0, "medium": 0, "low": 0}

    high = sum(1 for m in meals if m.confidence_score > 0.90)
    medium = sum(1 for m in meals if 0.70 <= m.confidence_score <= 0.90)
    low = sum(1 for m in meals if m.confidence_score < 0.70)
    total = len(meals)

    return {
        "high": round(100 * high / total, 1) if total > 0 else 0,
        "medium": round(100 * medium / total, 1) if total > 0 else 0,
        "low": round(100 * low / total, 1) if total > 0 else 0,
    }


def get_user_meals(user, date: str | None = None, limit: int | None = None, category: str | None = None):
    """Get user's meals, optionally filtered by date and category."""
    query = Meal.objects.filter(user=user)

    if date:
        try:
            parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
            start = timezone.make_aware(datetime.combine(parsed_date, datetime.min.time()))
            end = start + timedelta(days=1)
            query = query.filter(created_at__gte=start, created_at__lt=end)
        except ValueError:
            raise ValueError("date must be in YYYY-MM-DD format")

    if category:
        query = query.filter(meal_category=category)

    query = query.order_by("-created_at")
    if limit is not None:
        query = query[:limit]

    return list(query)


def _resolve_and_validate_items(raw_items: list[dict]) -> tuple[list[dict], list[str]]:
    """Validate each raw LLM item via MealItemCreateSerializer, resolve macros
    (IFCT/USDA/LLM-estimate), run the ±10% calorie sanity check. No DB write."""
    validated = []
    drop_warnings = []
    for raw in raw_items:
        try:
            from ..serializers import MealItemCreateSerializer
            normalized_raw = dict(raw)
            if "unit" in normalized_raw:
                normalized_raw["unit"] = normalize_unit(normalized_raw["unit"])
            serializer = MealItemCreateSerializer(data=normalized_raw)
            if serializer.is_valid():
                validated.append(serializer.validated_data)
            else:
                logger.warning("Dropping unparseable item: %r, errors: %s", raw, serializer.errors)
                item_name = raw.get("item_name", "an item")
                error_fields = ", ".join(serializer.errors.keys())
                drop_warnings.append(f"Could not add '{item_name}': invalid {error_fields}")
        except Exception as e:
            logger.warning("Error validating item %r: %s", raw, e)
            item_name = raw.get("item_name", "an item")
            drop_warnings.append(f"Could not add '{item_name}': unexpected error")
    validated = [resolve_item_macros(v) for v in validated]
    result = validate_macros(validated)
    return result["corrected_items"], drop_warnings + result["warnings"]


def _persist_meal(user, corrected_items: list[dict], *, original_text, transcription_text,
                   input_method: str, meal_category: str | None = None) -> Meal:
    """Create Meal + MealItem rows from already-resolved items."""
    confidence_score = sum(i.get("confidence", 0.85) for i in corrected_items) / len(corrected_items)
    resolved_category = meal_category or derive_meal_category_from_time(timezone.now())

    meal = Meal.objects.create(
        user=user,
        original_text=original_text,
        transcription_text=transcription_text,
        parsed_at=timezone.now(),
        confidence_score=confidence_score,
        input_method=input_method,
        meal_category=resolved_category,
    )

    for item_data in corrected_items:
        MealItem.objects.create(
            meal=meal,
            item_name=item_data["item_name"],
            quantity=item_data["quantity"],
            unit=item_data.get("unit", "serving"),
            serving_size_grams=item_data.get("serving_size_grams"),
            calories=item_data["calories"],
            protein_g=item_data["protein_g"],
            carbs_g=item_data["carbs_g"],
            fats_g=item_data["fats_g"],
            fiber_g=item_data.get("fiber_g", 0),
            confidence=item_data.get("confidence", 0.85),
            source=item_data.get("source") or "llm_estimate",
            llm_generated=True,
        )

    return meal


def _parse_audio_to_items(audio_path: str) -> dict:
    """Transcribe + parse + resolve. No DB write. Deletes audio_path when done."""
    try:
        transcript = transcribe(audio_path)
        raw_items = parse_meal(transcript)
        corrected_items, warnings = _resolve_and_validate_items(raw_items)
        for w in warnings:
            logger.warning("macro validation: %s", w)
        if not corrected_items:
            raise ValueError("No food items could be identified in the audio. Please try again with a clearer description of what you ate.")
        return {"items": corrected_items, "original_text": transcript, "transcription_text": transcript, "warnings": warnings}
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


def _parse_text_to_items(text: str) -> dict:
    """Parse text meal description. No DB write."""
    raw_items = parse_meal(text)
    corrected_items, warnings = _resolve_and_validate_items(raw_items)
    for w in warnings:
        logger.warning("macro validation: %s", w)
    if not corrected_items:
        raise ValueError("No food items could be identified in the text. Please describe what you ate more specifically.")
    return {"items": corrected_items, "original_text": text, "transcription_text": None, "warnings": warnings}


def _parse_image_to_items(image_path: str) -> dict:
    """Describe image via vision-LLM, parse, and resolve. No DB write. Deletes image_path when done."""
    try:
        description = scan_image(image_path)
        raw_items = parse_meal(description)
        corrected_items, warnings = _resolve_and_validate_items(raw_items)
        for w in warnings:
            logger.warning("macro validation: %s", w)
        if not corrected_items:
            raise ValueError("No food items could be identified in the photo. Please try a clearer photo of the food, label, or menu.")
        return {"items": corrected_items, "original_text": description, "transcription_text": description, "warnings": warnings}
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


def resolve_confirmed_items(items: list[dict]) -> tuple[list[dict], list[str]]:
    """Used by ConfirmMealView: re-resolve macros fresh for every item (never trusts
    client-sent macro fields), then run the calorie sanity check."""
    resolved = [resolve_item_macros(dict(item)) for item in items]
    result = validate_macros(resolved)
    return result["corrected_items"], result["warnings"]


def create_meal_from_audio(user, audio_path: str, category: str | None = None) -> Meal:
    """Create a meal from an audio file."""
    parsed = _parse_audio_to_items(audio_path)
    return _persist_meal(user, parsed["items"], original_text=parsed["original_text"],
                          transcription_text=parsed["transcription_text"], input_method="voice",
                          meal_category=category)


def create_meal_from_text(user, text: str, category: str | None = None) -> Meal:
    """Create a meal from typed text."""
    parsed = _parse_text_to_items(text)
    return _persist_meal(user, parsed["items"], original_text=parsed["original_text"],
                          transcription_text=parsed["transcription_text"], input_method="text",
                          meal_category=category)


def create_meal_from_image(user, image_path: str, category: str | None = None) -> Meal:
    """Create a meal from an uploaded photo via vision-LLM."""
    parsed = _parse_image_to_items(image_path)
    return _persist_meal(user, parsed["items"], original_text=parsed["original_text"],
                          transcription_text=parsed["transcription_text"], input_method="image",
                          meal_category=category)


def replace_meal_items(meal: Meal, payload_data: dict) -> Meal:
    """Replace meal items with rescale-or-relookup logic. Name unchanged -> rescale proportionally;
    name changed significantly -> re-run IFCT/USDA lookup."""
    from ..serializers import MealItemCreateSerializer

    old_items = list(meal.meal_items.all())

    validated = []
    for raw in payload_data.get("meal_items", []):
        try:
            serializer = MealItemCreateSerializer(data=raw)
            if serializer.is_valid():
                validated.append(serializer.validated_data)
            else:
                logger.warning("Dropping unparseable item in PATCH: %r, errors: %s", raw, serializer.errors)
        except Exception as e:
            logger.warning("Error validating item in PATCH %r: %s", raw, e)

    processed_items = []
    for idx, new_item in enumerate(validated):
        if idx < len(old_items):
            old_item = old_items[idx]
            if not needs_fresh_lookup(old_item.item_name, new_item["item_name"]):
                rescaled = rescale_item_macros(
                    {"calories": old_item.calories, "protein_g": old_item.protein_g,
                     "carbs_g": old_item.carbs_g, "fats_g": old_item.fats_g, "fiber_g": old_item.fiber_g},
                    old_quantity=old_item.quantity, old_unit=old_item.unit,
                    new_quantity=new_item["quantity"], new_unit=new_item.get("unit", "serving"),
                )
                if rescaled is not None:
                    processed_items.append({**new_item, **rescaled, "source": old_item.source,
                                             "confidence": old_item.confidence})
                    continue
        processed_items.append(resolve_item_macros(new_item))

    result = validate_macros(processed_items)
    for w in result["warnings"]:
        logger.warning("macro validation in PATCH: %s", w)
    corrected_items = result["corrected_items"]
    if not corrected_items:
        raise ValueError("Cannot update meal with zero items; delete it instead.")

    meal.meal_items.all().delete()

    for item_data in corrected_items:
        MealItem.objects.create(
            meal=meal,
            item_name=item_data["item_name"],
            quantity=item_data["quantity"],
            unit=item_data.get("unit", "serving"),
            serving_size_grams=item_data.get("serving_size_grams"),
            calories=item_data["calories"],
            protein_g=item_data["protein_g"],
            carbs_g=item_data["carbs_g"],
            fats_g=item_data["fats_g"],
            fiber_g=item_data.get("fiber_g", 0),
            confidence=item_data.get("confidence", 0.85),
            source=item_data.get("source") or "llm_estimate",
            llm_generated=True,
        )

    if payload_data.get("original_text"):
        meal.original_text = payload_data["original_text"]
    if payload_data.get("meal_category"):
        meal.meal_category = payload_data["meal_category"]

    meal.confidence_score = sum(i.get("confidence", 0.85) for i in corrected_items) / len(corrected_items)
    meal.save()

    return meal
