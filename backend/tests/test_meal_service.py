import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from bson import ObjectId
from app.services.meal_service import create_meal_from_audio


@pytest.fixture
def mock_audio_path(tmp_path):
    """Create a temporary audio file for testing."""
    audio_file = tmp_path / "test_audio.wav"
    audio_file.write_bytes(b"fake audio data")
    return str(audio_file)


class TestCreateMealFromAudio:
    @patch("app.services.meal_service.whisper_service.transcribe")
    @patch("app.services.meal_service.llm_service.parse_meal")
    def test_meal_items_use_llm_estimates_directly(
        self, mock_parse_meal, mock_transcribe,
        db, mock_audio_path
    ):
        """Test that meal items use LLM estimates directly without DB lookup."""
        user_id = "test_user"

        mock_transcribe.return_value = "I had a banana and some pizza"
        mock_parse_meal.return_value = [
            {
                "item_name": "banana",
                "quantity": 1,
                "unit": "medium",
                "serving_size_grams": 100,
                "calories": 89.0,
                "protein_g": 1.09,
                "carbs_g": 22.84,
                "fats_g": 0.33,
                "fiber_g": 2.6,
                "confidence": 0.9,
            },
            {
                "item_name": "pizza",
                "quantity": 2,
                "unit": "slices",
                "serving_size_grams": 250,
                "calories": 550,
                "protein_g": 15,
                "carbs_g": 60,
                "fats_g": 20,
                "fiber_g": 2,
                "confidence": 0.8,
            },
        ]

        meal = create_meal_from_audio(user_id, mock_audio_path, db)

        assert meal is not None
        assert len(meal["meal_items"]) == 2

        banana_item = meal["meal_items"][0]
        assert banana_item["item_name"] == "banana"
        assert banana_item["source"] == "llm_estimate"
        assert banana_item["confidence"] == 0.9
        assert banana_item["calories"] == 89.0

        pizza_item = meal["meal_items"][1]
        assert pizza_item["item_name"] == "pizza"
        assert pizza_item["source"] == "llm_estimate"
        assert pizza_item["confidence"] == 0.8
        # Macros validate: 15*4 + 60*4 + 20*9 = 60 + 240 + 180 = 480 cal (not 550)
        # nutrition_service corrects inconsistent macros to match calculated total
        assert pizza_item["calories"] == 480

    @patch("app.services.meal_service.whisper_service.transcribe")
    @patch("app.services.meal_service.llm_service.parse_meal")
    def test_validate_macros_runs_after_llm_parse(
        self, mock_parse_meal, mock_transcribe,
        db, mock_audio_path
    ):
        """Test that validate_macros still corrects inconsistent macros post-lookup."""
        user_id = "test_user"

        mock_transcribe.return_value = "I had a banana"
        mock_parse_meal.return_value = [
            {
                "item_name": "banana",
                "quantity": 1,
                "unit": "medium",
                "serving_size_grams": 100,
                "calories": 200,
                "protein_g": 1.09,
                "carbs_g": 22.84,
                "fats_g": 0.33,
                "fiber_g": 2.6,
                "confidence": 0.8,
            },
        ]

        meal = create_meal_from_audio(user_id, mock_audio_path, db)

        banana_item = meal["meal_items"][0]
        expected_calories = round((1.09 * 4 + 22.84 * 4 + 0.33 * 9) / 5) * 5
        assert banana_item["calories"] == expected_calories

    @patch("app.services.meal_service.whisper_service.transcribe")
    @patch("app.services.meal_service.llm_service.parse_meal")
    def test_source_field_in_response(
        self, mock_parse_meal, mock_transcribe,
        db, mock_audio_path
    ):
        """Test that source field is correctly set to llm_estimate in the meal response."""
        user_id = "test_user"

        mock_transcribe.return_value = "I ate a banana"
        mock_parse_meal.return_value = [
            {
                "item_name": "banana",
                "quantity": 1,
                "unit": "medium",
                "serving_size_grams": 100,
                "calories": 89.0,
                "protein_g": 1.09,
                "carbs_g": 22.84,
                "fats_g": 0.33,
                "fiber_g": 2.6,
                "confidence": 0.85,
            },
        ]

        meal = create_meal_from_audio(user_id, mock_audio_path, db)

        assert meal["meal_items"][0]["source"] == "llm_estimate"

        saved_meal = db.meals.find_one({"_id": meal["_id"]})
        assert saved_meal["meal_items"][0]["source"] == "llm_estimate"
