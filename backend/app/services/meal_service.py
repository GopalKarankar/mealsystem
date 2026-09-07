import logging
import os
from datetime import datetime, timedelta
from bson import ObjectId
from pydantic import ValidationError

from app.config import settings
from app.schemas import MealItemCreate, MealResponse, MealItemResponse, MealUpdate
from app.services import whisper_service, llm_service, nutrition_service

logger = logging.getLogger(__name__)

ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".webm"}


def get_confidence_badge(score: float) -> str:
    if score > 0.90:
        return "green"
    elif score >= 0.70:
        return "orange"
    else:
        return "red"


def calculate_daily_totals(meals: list[dict]) -> dict:
    totals = {
        "calories": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fats_g": 0.0,
        "fiber_g": 0.0,
    }
    for meal in meals:
        for item in meal["meal_items"]:
            totals["calories"] += item["calories"]
            totals["protein_g"] += item["protein_g"]
            totals["carbs_g"] += item["carbs_g"]
            totals["fats_g"] += item["fats_g"]
            totals["fiber_g"] += item.get("fiber_g", 0)
    return totals


def calculate_confidence_distribution(meals: list[dict]) -> dict:
    if not meals:
        return {"high": 0, "medium": 0, "low": 0}

    high = sum(1 for m in meals if m["confidence_score"] > 0.90)
    medium = sum(1 for m in meals if 0.70 <= m["confidence_score"] <= 0.90)
    low = sum(1 for m in meals if m["confidence_score"] < 0.70)
    total = len(meals)

    return {
        "high": round(100 * high / total, 1) if total > 0 else 0,
        "medium": round(100 * medium / total, 1) if total > 0 else 0,
        "low": round(100 * low / total, 1) if total > 0 else 0,
    }


def get_user_meals(user_id, date: str | None, limit: int | None, db) -> list[dict]:
    query = {"user_id": user_id}

    if date:
        try:
            parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
            start = datetime.combine(parsed_date, datetime.min.time())
            end = start + timedelta(days=1)
            query["created_at"] = {"$gte": start, "$lt": end}
        except ValueError:
            raise ValueError("date must be in YYYY-MM-DD format")

    cursor = db.meals.find(query).sort("created_at", -1)
    if limit is not None:
        cursor = cursor.limit(limit)

    return list(cursor)


def create_meal_from_audio(user_id, audio_path: str, db) -> dict:
    try:
        transcript = whisper_service.transcribe(audio_path)
        raw_items = llm_service.parse_meal(transcript)

        validated = []
        for raw in raw_items:
            try:
                item_schema = MealItemCreate(**raw)
                validated.append(item_schema)
            except ValidationError as e:
                logger.warning("Dropping unparseable item from LLM output: %r, error: %s", raw, e)

        looked_up_items = [v.model_dump() for v in validated]

        result = nutrition_service.validate_macros(looked_up_items)
        for w in result["warnings"]:
            logger.warning("macro validation: %s", w)

        corrected_items = result["corrected_items"]
        if not corrected_items:
            raise ValueError(
                "No food items could be identified in the audio. Please try again with a clearer description of what you ate."
            )

        confidence_score = sum(
            i.get("confidence", 0.85) for i in corrected_items
        ) / len(corrected_items)

        meal_doc = {
            "user_id": user_id,
            "original_text": transcript,
            "transcription_text": transcript,
            "parsed_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "confidence_score": confidence_score,
            "meal_items": [
                {
                    "_id": ObjectId(),
                    "item_name": item_data["item_name"],
                    "quantity": item_data["quantity"],
                    "unit": item_data["unit"],
                    "serving_size_grams": item_data.get("serving_size_grams"),
                    "calories": item_data["calories"],
                    "protein_g": item_data["protein_g"],
                    "carbs_g": item_data["carbs_g"],
                    "fats_g": item_data["fats_g"],
                    "fiber_g": item_data.get("fiber_g", 0),
                    "confidence": item_data.get("confidence", 0.85),
                    "source": item_data.get("source") or "llm_estimate",
                    "llm_generated": True,
                }
                for item_data in corrected_items
            ],
        }

        result = db.meals.insert_one(meal_doc)
        meal_doc["_id"] = result.inserted_id

        return meal_doc

    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


def replace_meal_items(meal: dict, payload: MealUpdate, db) -> dict:
    validated = []
    for raw in payload.meal_items:
        try:
            item_schema = MealItemCreate(**raw.model_dump())
            validated.append(item_schema)
        except ValidationError as e:
            logger.warning("Dropping unparseable item in PATCH: %r, error: %s", raw, e)

    result = nutrition_service.validate_macros([v.model_dump() for v in validated])
    for w in result["warnings"]:
        logger.warning("macro validation in PATCH: %s", w)

    corrected_items = result["corrected_items"]
    if not corrected_items:
        raise ValueError("Cannot update meal with zero items; delete it instead.")

    confidence_score = sum(
        i.get("confidence", 0.85) for i in corrected_items
    ) / len(corrected_items)

    new_items = [
        {
            "_id": ObjectId(),
            "item_name": item_data["item_name"],
            "quantity": item_data["quantity"],
            "unit": item_data["unit"],
            "serving_size_grams": item_data.get("serving_size_grams"),
            "calories": item_data["calories"],
            "protein_g": item_data["protein_g"],
            "carbs_g": item_data["carbs_g"],
            "fats_g": item_data["fats_g"],
            "fiber_g": item_data.get("fiber_g", 0),
            "confidence": item_data.get("confidence", 0.85),
            "source": "llm_estimate",
            "llm_generated": True,
        }
        for item_data in corrected_items
    ]

    update_fields = {"meal_items": new_items, "confidence_score": confidence_score, "updated_at": datetime.utcnow()}
    if payload.original_text:
        update_fields["original_text"] = payload.original_text

    db.meals.update_one({"_id": meal["_id"]}, {"$set": update_fields})
    meal.update(update_fields)

    return meal


def serialize_meal(meal: dict) -> MealResponse:
    items = [
        MealItemResponse(
            id=str(i["_id"]),
            item_name=i["item_name"],
            quantity=i["quantity"],
            unit=i["unit"],
            serving_size_grams=i.get("serving_size_grams"),
            calories=i["calories"],
            protein_g=i["protein_g"],
            carbs_g=i["carbs_g"],
            fats_g=i["fats_g"],
            fiber_g=i.get("fiber_g", 0),
            confidence=i.get("confidence", 0.85),
            source=i.get("source", "llm_estimate"),
        )
        for i in meal["meal_items"]
    ]

    totals_dict = {
        "calories": sum(i["calories"] for i in meal["meal_items"]),
        "protein_g": sum(i["protein_g"] for i in meal["meal_items"]),
        "carbs_g": sum(i["carbs_g"] for i in meal["meal_items"]),
        "fats_g": sum(i["fats_g"] for i in meal["meal_items"]),
        "fiber_g": sum(i.get("fiber_g", 0) for i in meal["meal_items"]),
    }

    return MealResponse(
        meal_id=str(meal["_id"]),
        original_text=meal["original_text"],
        transcription_text=meal.get("transcription_text"),
        confidence_score=meal["confidence_score"],
        confidence_badge=get_confidence_badge(meal["confidence_score"]),
        parsed_at=meal["parsed_at"],
        meal_items=items,
        totals=totals_dict,
        created_at=meal["created_at"],
    )


