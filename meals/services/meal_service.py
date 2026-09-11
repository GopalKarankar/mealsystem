import logging
import os
from datetime import datetime, timedelta
from django.utils import timezone

from .whisper_service import transcribe
from .llm_service import parse_meal, LLMServiceError
from .nutrition_service import validate_macros
from .vision_service import scan_image
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


def _assemble_meal(user, raw_items: list, *, original_text: str, transcription_text: str | None,
                    input_method: str, empty_items_message: str, meal_category: str | None = None) -> Meal:
    """Shared logic for assembling a meal from parsed items."""
    validated = []
    for raw in raw_items:
        try:
            from ..serializers import MealItemCreateSerializer
            serializer = MealItemCreateSerializer(data=raw)
            if serializer.is_valid():
                validated.append(serializer.validated_data)
            else:
                logger.warning("Dropping unparseable item from LLM output: %r, errors: %s", raw, serializer.errors)
        except Exception as e:
            logger.warning("Error validating item %r: %s", raw, e)

    result = validate_macros(validated)
    for w in result["warnings"]:
        logger.warning("macro validation: %s", w)

    corrected_items = result["corrected_items"]
    if not corrected_items:
        raise ValueError(empty_items_message)

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


def create_meal_from_audio(user, audio_path: str, category: str | None = None) -> Meal:
    """Create a meal from an audio file."""
    try:
        transcript = transcribe(audio_path)
        raw_items = parse_meal(transcript)
        return _assemble_meal(
            user, raw_items,
            original_text=transcript,
            transcription_text=transcript,
            input_method="voice",
            empty_items_message="No food items could be identified in the audio. Please try again with a clearer description of what you ate.",
            meal_category=category,
        )
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


def create_meal_from_text(user, text: str, category: str | None = None) -> Meal:
    """Create a meal from typed text."""
    raw_items = parse_meal(text)
    return _assemble_meal(
        user, raw_items,
        original_text=text,
        transcription_text=None,
        input_method="text",
        empty_items_message="No food items could be identified in the text. Please describe what you ate more specifically.",
        meal_category=category,
    )


def create_meal_from_image(user, image_path: str, category: str | None = None) -> Meal:
    """Create a meal from an uploaded photo via vision-LLM."""
    try:
        description = scan_image(image_path)
        raw_items = parse_meal(description)
        return _assemble_meal(
            user, raw_items,
            original_text=description,
            transcription_text=description,
            input_method="image",
            empty_items_message="No food items could be identified in the photo. Please try a clearer photo of the food, label, or menu.",
            meal_category=category,
        )
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


def replace_meal_items(meal: Meal, payload_data: dict) -> Meal:
    """Replace meal items and recalculate confidence score."""
    from ..serializers import MealItemCreateSerializer

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

    result = validate_macros(validated)
    for w in result["warnings"]:
        logger.warning("macro validation in PATCH: %s", w)

    corrected_items = result["corrected_items"]
    if not corrected_items:
        raise ValueError("Cannot update meal with zero items; delete it instead.")

    confidence_score = sum(i.get("confidence", 0.85) for i in corrected_items) / len(corrected_items)

    # Delete old items
    meal.meal_items.all().delete()

    # Create new items
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
            source="llm_estimate",
            llm_generated=True,
        )

    # Update meal metadata
    if payload_data.get("original_text"):
        meal.original_text = payload_data["original_text"]
    if payload_data.get("meal_category"):
        meal.meal_category = payload_data["meal_category"]

    meal.confidence_score = confidence_score
    meal.save()

    return meal
