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
from .serializers import MealSerializer, MealUpdateSerializer, DashboardSerializer, MealTextInputSerializer
from .services.meal_service import (
    create_meal_from_audio,
    create_meal_from_text,
    create_meal_from_image,
    get_user_meals,
    replace_meal_items,
    get_confidence_badge,
    calculate_daily_totals,
    calculate_confidence_distribution,
    ALLOWED_AUDIO_EXTENSIONS,
    ALLOWED_IMAGE_EXTENSIONS,
    sniff_image_extension,
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

        # Validate category if provided
        category = request.query_params.get('category')
        if category and category not in dict(Meal.MEAL_CATEGORY_CHOICES):
            return Response(
                {"detail": "Invalid meal_category"},
                status=status.HTTP_400_BAD_REQUEST
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
                meal = create_meal_from_audio(request.user, temp_path, category=category)
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


class CreateMealTextView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = MealTextInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": "Please enter a description of what you ate (max 2000 characters)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        text = serializer.validated_data['text']
        category = serializer.validated_data.get('category')

        try:
            meal = create_meal_from_text(request.user, text, category=category)
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
        except Exception:
            logger.exception("Unexpected error processing text meal")
            return Response(
                {"detail": "Failed to process text"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(MealSerializer(meal).data, status=status.HTTP_201_CREATED)


class CreateMealImageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if 'file' not in request.FILES:
            return Response(
                {"detail": "No image file provided"},
                status=status.HTTP_400_BAD_REQUEST
            )

        file = request.FILES['file']
        ext = os.path.splitext(file.name or "")[1].lower()

        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            return Response(
                {"detail": f"Unsupported image format '{ext}'. Allowed: jpg, jpeg, png, webp"},
                status=status.HTTP_400_BAD_REQUEST
            )

        max_bytes = settings.MAX_IMAGE_SIZE_MB * 1024 * 1024
        if file.size > max_bytes:
            return Response(
                {"detail": f"Image exceeds {settings.MAX_IMAGE_SIZE_MB}MB limit"},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            )

        sniffed_ext = sniff_image_extension(file)
        if sniffed_ext is None:
            return Response(
                {"detail": "File does not appear to be a valid image"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate category if provided
        category = request.query_params.get('category')
        if category and category not in dict(Meal.MEAL_CATEGORY_CHOICES):
            return Response(
                {"detail": "Invalid meal_category"},
                status=status.HTTP_400_BAD_REQUEST
            )

        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        temp_path = os.path.join(
            settings.UPLOAD_DIR,
            f"{request.user.id}_{uuid.uuid4().hex}{sniffed_ext}"
        )

        try:
            with open(temp_path, 'wb') as f:
                for chunk in file.chunks():
                    f.write(chunk)

            try:
                meal = create_meal_from_image(request.user, temp_path, category=category)
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
            except Exception:
                logger.exception("Unexpected error processing image meal")
                return Response(
                    {"detail": "Failed to process image"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            return Response(MealSerializer(meal).data, status=status.HTTP_201_CREATED)

        except Exception:
            logger.exception("Error in image upload")
            return Response(
                {"detail": "Failed to process image"},
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
        category = request.query_params.get('category')

        try:
            limit = int(limit)
            if limit < 1 or limit > 100:
                limit = 50
        except (ValueError, TypeError):
            limit = 50

        try:
            meals = get_user_meals(request.user, date=date_str, limit=limit, category=category)
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = MealSerializer(meals, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MealDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_meal_or_error(self, meal_id, user):
        try:
            meal_id_int = int(meal_id)
        except ValueError:
            return None, Response(
                {"detail": "Invalid meal id"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            meal = Meal.objects.get(id=meal_id_int)
        except Meal.DoesNotExist:
            return None, Response(
                {"detail": "Meal not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        if meal.user != user:
            return None, Response(
                {"detail": "Not authorized to access this meal"},
                status=status.HTTP_403_FORBIDDEN
            )

        return meal, None

    def patch(self, request, meal_id):
        meal, error = self._get_meal_or_error(meal_id, request.user)
        if error:
            return error

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

    def delete(self, request, meal_id):
        meal, error = self._get_meal_or_error(meal_id, request.user)
        if error:
            return error

        meal.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# Keep old views for backwards compatibility if needed elsewhere
class UpdateMealView(MealDetailView):
    pass


class DeleteMealView(MealDetailView):
    pass


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str = request.query_params.get('date')
        category_str = request.query_params.get('category')

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

        # Compute category counts from unfiltered meals
        category_counts = {choice: 0 for choice, _ in Meal.MEAL_CATEGORY_CHOICES}
        for m in day_meals:
            category_counts[m.meal_category] = category_counts.get(m.meal_category, 0) + 1

        # Filter by category if requested
        filtered_meals = [m for m in day_meals if not category_str or m.meal_category == category_str]
        recent_meals = filtered_meals[:7]

        # Calculate totals from filtered meals
        totals = calculate_daily_totals(filtered_meals)
        totals["confidence_distribution"] = calculate_confidence_distribution(filtered_meals)

        response_data = {
            "date": date_str,
            "meals": MealSerializer(recent_meals, many=True).data,
            "daily_totals": totals,
            "category_counts": category_counts,
        }

        return Response(response_data, status=status.HTTP_200_OK)
