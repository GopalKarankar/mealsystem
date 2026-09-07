import logging
import os
import uuid
from datetime import datetime
from typing import List, Optional
from bson import ObjectId
from bson.errors import InvalidId

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status

from app.auth.dependencies import get_current_user
from app.config import settings
from app.database import get_db
from app.schemas import MealResponse, MealUpdate, DashboardResponse
from app.services import meal_service
from app.services.llm_service import LLMServiceError

logger = logging.getLogger(__name__)

router = APIRouter()
dashboard_router = APIRouter()


@router.post("/voice", response_model=MealResponse, status_code=status.HTTP_201_CREATED)
def create_meal_voice(
    file: UploadFile = File(...),
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in meal_service.ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio format '{ext}'. Allowed: wav, mp3, m4a, webm",
        )

    os.makedirs(settings.upload_dir, exist_ok=True)
    temp_path = os.path.join(settings.upload_dir, f"{current_user['_id']}_{uuid.uuid4().hex}{ext}")
    max_bytes = settings.max_audio_size_mb * 1024 * 1024
    size = 0

    try:
        with open(temp_path, "wb") as out:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    out.close()
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Audio exceeds {settings.max_audio_size_mb}MB limit",
                    )
                out.write(chunk)

        try:
            try:
                meal = meal_service.create_meal_from_audio(current_user["_id"], temp_path, db)
            except LLMServiceError as e:
                logger.error("LLM service failure during voice meal creation: %s", e)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=str(e),
                )
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=str(e),
                )
            except Exception:
                logger.exception("Unexpected error processing voice meal")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to process audio",
                )

            return meal_service.serialize_meal(meal)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        logger.exception("Error in voice upload: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process audio",
        )


@router.get("", response_model=List[MealResponse])
def list_meals(
    date: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        meals = meal_service.get_user_meals(current_user["_id"], date, limit, db)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date must be in YYYY-MM-DD format",
        )

    return [meal_service.serialize_meal(m) for m in meals]


@router.patch("/{meal_id}", response_model=MealResponse)
def update_meal(
    meal_id: str,
    payload: MealUpdate,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        oid = ObjectId(meal_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid meal id",
        )

    meal = db.meals.find_one({"_id": oid})
    if meal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal not found",
        )

    if meal["user_id"] != current_user["_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this meal",
        )

    try:
        meal = meal_service.replace_meal_items(meal, payload, db)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        )

    return meal_service.serialize_meal(meal)


@router.delete("/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meal(
    meal_id: str,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        oid = ObjectId(meal_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid meal id",
        )

    meal = db.meals.find_one({"_id": oid})
    if meal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal not found",
        )

    if meal["user_id"] != current_user["_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this meal",
        )

    db.meals.delete_one({"_id": oid})

    return None


@dashboard_router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    date: str = Query(...),
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date must be in YYYY-MM-DD format",
        )

    day_meals = meal_service.get_user_meals(current_user["_id"], date, None, db)
    recent = day_meals[:7]
    totals = meal_service.calculate_daily_totals(day_meals)
    totals["confidence_distribution"] = meal_service.calculate_confidence_distribution(day_meals)

    return DashboardResponse(
        date=date,
        meals=[meal_service.serialize_meal(m) for m in recent],
        daily_totals=totals,
    )
