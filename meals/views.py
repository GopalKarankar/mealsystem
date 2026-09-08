import logging
import os
import uuid
from datetime import datetime
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import Meal, MealItem
from .serializers import MealSerializer, MealUpdateSerializer, DashboardSerializer
from .services.meal_service import (
    create_meal_from_audio,
    get_user_meals,
    replace_meal_items,
    get_confidence_badge,
    calculate_daily_totals,
    calculate_confidence_distribution,
    ALLOWED_AUDIO_EXTENSIONS,
)
from .services.llm_service import LLMServiceError
from django.conf import settings

logger = logging.getLogger(__name__)


class CreateMealVoiceView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if 'file' not in request.FILES:
            return Response(
                {"detail": "No audio file provided"},
                status=status.HTTP_400_BAD_REQUEST
            )

        file = request.FILES['file']
        ext = os.path.splitext(file.name or "")[1].lower()

        if ext not in ALLOWED_AUDIO_EXTENSIONS:
            return Response(
                {"detail": f"Unsupported audio format '{ext}'. Allowed: wav, mp3, m4a, webm"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check file size
        max_bytes = settings.MAX_AUDIO_SIZE_MB * 1024 * 1024
        if file.size > max_bytes:
            return Response(
                {"detail": f"Audio exceeds {settings.MAX_AUDIO_SIZE_MB}MB limit"},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            )

        # Create temporary file
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        temp_path = os.path.join(
            settings.UPLOAD_DIR,
            f"{request.user.id}_{uuid.uuid4().hex}{ext}"
        )

        try:
            # Save uploaded file
            with open(temp_path, 'wb') as f:
                for chunk in file.chunks():
                    f.write(chunk)

            # Process audio through meal service
            try:
                meal = create_meal_from_audio(request.user, temp_path)
            except LLMServiceError as e:
                logger.error("LLM service failure: %s", e)
                return Response(
                    {"detail": str(e)},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            except ValueError as e:
                return Response(
                    {"detail": str(e)},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY
                )
            except Exception as e:
                logger.exception("Unexpected error processing voice meal")
                return Response(
                    {"detail": "Failed to process audio"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            serializer = MealSerializer(meal)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception("Error in voice upload: %s", e)
            return Response(
                {"detail": "Failed to process audio"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass


class ListMealsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str = request.query_params.get('date')
        limit = request.query_params.get('limit', 50)

        try:
            limit = int(limit)
            if limit < 1 or limit > 100:
                limit = 50
        except (ValueError, TypeError):
            limit = 50

        try:
            meals = get_user_meals(request.user, date=date_str, limit=limit)
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = MealSerializer(meals, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UpdateMealView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, meal_id):
        # Validate meal_id format (should be numeric string)
        try:
            meal_id_int = int(meal_id)
        except ValueError:
            return Response(
                {"detail": "Invalid meal id"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            meal = Meal.objects.get(id=meal_id_int)
        except Meal.DoesNotExist:
            return Response(
                {"detail": "Meal not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check ownership
        if meal.user != request.user:
            return Response(
                {"detail": "Not authorized to modify this meal"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Validate request data
        serializer = MealUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            meal = replace_meal_items(meal, serializer.validated_data)
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )

        response_serializer = MealSerializer(meal)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class DeleteMealView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, meal_id):
        # Validate meal_id format
        try:
            meal_id_int = int(meal_id)
        except ValueError:
            return Response(
                {"detail": "Invalid meal id"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            meal = Meal.objects.get(id=meal_id_int)
        except Meal.DoesNotExist:
            return Response(
                {"detail": "Meal not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check ownership
        if meal.user != request.user:
            return Response(
                {"detail": "Not authorized to delete this meal"},
                status=status.HTTP_403_FORBIDDEN
            )

        meal.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str = request.query_params.get('date')

        if not date_str:
            return Response(
                {"detail": "date parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate date format
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return Response(
                {"detail": "date must be in YYYY-MM-DD format"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            day_meals = get_user_meals(request.user, date=date_str, limit=None)
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get first 7 meals for display
        recent_meals = day_meals[:7]

        # Calculate totals
        totals = calculate_daily_totals(day_meals)
        totals["confidence_distribution"] = calculate_confidence_distribution(day_meals)

        response_data = {
            "date": date_str,
            "meals": MealSerializer(recent_meals, many=True).data,
            "daily_totals": totals,
        }

        return Response(response_data, status=status.HTTP_200_OK)
