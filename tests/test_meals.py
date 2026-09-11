import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.utils import timezone
from accounts.models import User
from meals.models import Meal, MealItem
from accounts.jwt import create_access_token
from meals.services.llm_service import LLMServiceError


@pytest.mark.django_db
class TestMealEndpoints:
    def setup_method(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.token = create_access_token(
            data={"sub": str(self.user.id)},
            expires_delta=timedelta(seconds=604800),
        )
        self.headers = {'HTTP_AUTHORIZATION': f'Bearer {self.token}'}

    def test_list_meals_unauthorized(self):
        """Test listing meals requires authentication."""
        response = self.client.get('/meals/')
        assert response.status_code == 403 or response.status_code == 401

    def test_list_meals_empty(self):
        """Test listing meals when no meals exist."""
        response = self.client.get('/meals/', **self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_meals_with_data(self):
        """Test listing meals returns user's meals."""
        # Create a meal
        meal = Meal.objects.create(
            user=self.user,
            original_text="I ate a banana",
            transcription_text="I ate a banana",
            confidence_score=0.85,
        )
        MealItem.objects.create(
            meal=meal,
            item_name="banana",
            quantity=1,
            unit="medium",
            calories=89,
            protein_g=1.09,
            carbs_g=22.84,
            fats_g=0.33,
        )

        response = self.client.get('/meals/', **self.headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]['meal_items'][0]['item_name'] == 'banana'

    def test_list_meals_with_date_filter(self):
        """Test listing meals filtered by date."""
        today = timezone.now().date()

        # Create meal for today (auto_now_add ignores created_at arg, so update it after)
        meal_today = Meal.objects.create(
            user=self.user,
            original_text="Today meal",
            transcription_text="Today meal",
            confidence_score=0.85,
        )
        meal_today.created_at = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        meal_today.save(update_fields=['created_at'])

        # Create meal for yesterday
        yesterday = today - timedelta(days=1)
        meal_yesterday = Meal.objects.create(
            user=self.user,
            original_text="Yesterday meal",
            transcription_text="Yesterday meal",
            confidence_score=0.85,
        )
        meal_yesterday.created_at = timezone.make_aware(datetime.combine(yesterday, datetime.min.time()))
        meal_yesterday.save(update_fields=['created_at'])

        date_str = today.strftime("%Y-%m-%d")
        response = self.client.get(f'/meals/?date={date_str}', **self.headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert "Today meal" in data[0]['original_text']

    def test_list_meals_with_invalid_date(self):
        """Test listing meals with invalid date format."""
        response = self.client.get('/meals/?date=invalid-date', **self.headers)
        assert response.status_code == 400

    def test_dashboard_requires_date(self):
        """Test dashboard endpoint requires date parameter."""
        response = self.client.get('/meals/dashboard', **self.headers)
        assert response.status_code == 400

    def test_dashboard_with_valid_date(self):
        """Test dashboard returns totals and meals."""
        today = timezone.now().date()
        date_str = today.strftime("%Y-%m-%d")

        # Create meal (auto_now_add ignores created_at arg, so update it after)
        meal = Meal.objects.create(
            user=self.user,
            original_text="Test meal",
            transcription_text="Test meal",
            confidence_score=0.85,
        )
        meal.created_at = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        meal.save(update_fields=['created_at'])

        MealItem.objects.create(
            meal=meal,
            item_name="banana",
            quantity=1,
            unit="medium",
            calories=89,
            protein_g=1.09,
            carbs_g=22.84,
            fats_g=0.33,
        )

        response = self.client.get(f'/meals/dashboard?date={date_str}', **self.headers)
        assert response.status_code == 200
        data = response.json()
        assert data['date'] == date_str
        assert 'meals' in data
        assert 'daily_totals' in data
        assert data['daily_totals']['calories'] == 89

    def test_delete_meal_unauthorized(self):
        """Test deleting another user's meal fails."""
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='pass123'
        )
        meal = Meal.objects.create(
            user=other_user,
            original_text="Other user meal",
            transcription_text="Other user meal",
            confidence_score=0.85,
        )

        response = self.client.delete(f'/meals/{meal.id}', **self.headers)
        assert response.status_code == 403

    def test_delete_meal_not_found(self):
        """Test deleting non-existent meal returns 404."""
        response = self.client.delete('/meals/99999', **self.headers)
        assert response.status_code == 404

    def test_delete_meal_success(self):
        """Test successfully deleting a meal."""
        meal = Meal.objects.create(
            user=self.user,
            original_text="Meal to delete",
            transcription_text="Meal to delete",
            confidence_score=0.85,
        )

        response = self.client.delete(f'/meals/{meal.id}', **self.headers)
        assert response.status_code == 204

        # Verify meal is deleted
        assert not Meal.objects.filter(id=meal.id).exists()

    def test_update_meal_invalid_format(self):
        """Test updating meal with non-numeric ID."""
        response = self.client.patch(
            '/meals/invalid-id',
            data=json.dumps({'meal_items': []}),
            content_type='application/json',
            **self.headers
        )
        assert response.status_code == 400

    def test_update_meal_not_found(self):
        """Test updating non-existent meal."""
        response = self.client.patch(
            '/meals/99999',
            data=json.dumps({'meal_items': [
                {
                    'item_name': 'banana',
                    'quantity': 1,
                    'unit': 'piece',
                    'calories': 89,
                    'protein_g': 1.09,
                    'carbs_g': 22.84,
                    'fats_g': 0.33,
                }
            ]}),
            content_type='application/json',
            **self.headers
        )
        assert response.status_code == 404

    def test_update_meal_unauthorized(self):
        """Test updating another user's meal fails."""
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='pass123'
        )
        meal = Meal.objects.create(
            user=other_user,
            original_text="Other user meal",
            transcription_text="Other user meal",
            confidence_score=0.85,
        )

        response = self.client.patch(
            f'/meals/{meal.id}',
            data=json.dumps({'meal_items': [
                {
                    'item_name': 'banana',
                    'quantity': 1,
                    'unit': 'piece',
                    'calories': 89,
                    'protein_g': 1.09,
                    'carbs_g': 22.84,
                    'fats_g': 0.33,
                }
            ]}),
            content_type='application/json',
            **self.headers
        )
        assert response.status_code == 403

    def test_update_meal_success(self):
        """Test successfully updating a meal."""
        meal = Meal.objects.create(
            user=self.user,
            original_text="Original meal",
            transcription_text="Original meal",
            confidence_score=0.85,
        )
        MealItem.objects.create(
            meal=meal,
            item_name="old item",
            quantity=1,
            unit="serving",
            calories=100,
            protein_g=10,
            carbs_g=10,
            fats_g=5,
        )

        response = self.client.patch(
            f'/meals/{meal.id}',
            data=json.dumps({
                'original_text': 'Updated meal',
                'meal_items': [
                    {
                        'item_name': 'banana',
                        'quantity': 1,
                        'unit': 'piece',
                        'calories': 89,
                        'protein_g': 1.09,
                        'carbs_g': 22.84,
                        'fats_g': 0.33,
                    }
                ]
            }),
            content_type='application/json',
            **self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data['original_text'] == 'Updated meal'
        assert len(data['meal_items']) == 1
        assert data['meal_items'][0]['item_name'] == 'banana'

    def test_voice_no_file_provided(self):
        """Test voice upload requires a 'file' field."""
        response = self.client.post('/meals/voice', {}, **self.headers)
        assert response.status_code == 400
        assert 'No audio file' in response.json()['detail']

    def test_voice_unsupported_extension(self):
        """Test voice upload rejects disallowed audio formats."""
        audio = SimpleUploadedFile('recording.txt', b'not audio', content_type='text/plain')
        response = self.client.post('/meals/voice', {'file': audio}, **self.headers)
        assert response.status_code == 400
        assert 'Unsupported audio format' in response.json()['detail']

    @override_settings(MAX_AUDIO_SIZE_MB=0)
    def test_voice_file_too_large(self):
        """Test voice upload rejects files over the configured size limit."""
        audio = SimpleUploadedFile('recording.wav', b'x' * 100, content_type='audio/wav')
        response = self.client.post('/meals/voice', {'file': audio}, **self.headers)
        assert response.status_code == 413

    @patch('meals.services.meal_service.parse_meal')
    @patch('meals.services.meal_service.transcribe')
    def test_voice_no_items_identified_returns_422(self, mock_transcribe, mock_parse_meal):
        """Test voice upload returns 422 when no food items can be identified."""
        mock_transcribe.return_value = "um"
        mock_parse_meal.return_value = []

        audio = SimpleUploadedFile('recording.wav', b'fake wav bytes', content_type='audio/wav')
        response = self.client.post('/meals/voice', {'file': audio}, **self.headers)
        assert response.status_code == 422
        assert 'No food items could be identified' in response.json()['detail']

    @patch('meals.services.meal_service.parse_meal')
    @patch('meals.services.meal_service.transcribe')
    def test_voice_llm_service_error_returns_503(self, mock_transcribe, mock_parse_meal):
        """Test voice upload returns 503 when the LLM service fails."""
        mock_transcribe.return_value = "I ate a banana"
        mock_parse_meal.side_effect = LLMServiceError("Groq API unavailable")

        audio = SimpleUploadedFile('recording.wav', b'fake wav bytes', content_type='audio/wav')
        response = self.client.post('/meals/voice', {'file': audio}, **self.headers)
        assert response.status_code == 503
        assert 'Groq API unavailable' in response.json()['detail']

    @patch('meals.services.meal_service.parse_meal')
    @patch('meals.services.meal_service.transcribe')
    def test_voice_success_creates_meal(self, mock_transcribe, mock_parse_meal):
        """Test successful voice upload creates a meal with parsed items."""
        mock_transcribe.return_value = "I ate a banana"
        mock_parse_meal.return_value = [
            {
                'item_name': 'banana',
                'quantity': 1,
                'unit': 'piece',
                'calories': 89,
                'protein_g': 1.09,
                'carbs_g': 22.84,
                'fats_g': 0.33,
            }
        ]

        audio = SimpleUploadedFile('recording.wav', b'fake wav bytes', content_type='audio/wav')
        response = self.client.post('/meals/voice', {'file': audio}, **self.headers)
        assert response.status_code == 201
        data = response.json()
        assert len(data['meal_items']) == 1
        assert data['meal_items'][0]['item_name'] == 'banana'
        assert data['input_method'] == 'voice'
        assert Meal.objects.filter(user=self.user).count() == 1

    def test_text_missing_field(self):
        """Test text endpoint requires 'text' field."""
        response = self.client.post(
            '/meals/text', {},
            content_type='application/json',
            **self.headers
        )
        assert response.status_code == 400

    def test_text_empty_string(self):
        """Test text endpoint rejects empty or whitespace-only strings."""
        response = self.client.post(
            '/meals/text',
            data=json.dumps({'text': '   '}),
            content_type='application/json',
            **self.headers
        )
        assert response.status_code == 400

    def test_text_too_long(self):
        """Test text endpoint rejects strings over 2000 characters."""
        response = self.client.post(
            '/meals/text',
            data=json.dumps({'text': 'a' * 2001}),
            content_type='application/json',
            **self.headers
        )
        assert response.status_code == 400

    @patch('meals.services.meal_service.parse_meal')
    def test_text_no_items_identified_returns_422(self, mock_parse_meal):
        """Test text endpoint returns 422 when no food items identified."""
        mock_parse_meal.return_value = []
        response = self.client.post(
            '/meals/text',
            data=json.dumps({'text': 'asdf'}),
            content_type='application/json',
            **self.headers
        )
        assert response.status_code == 422

    @patch('meals.services.meal_service.parse_meal')
    def test_text_llm_service_error_returns_503(self, mock_parse_meal):
        """Test text endpoint returns 503 when LLM fails."""
        mock_parse_meal.side_effect = LLMServiceError("Groq API unavailable")
        response = self.client.post(
            '/meals/text',
            data=json.dumps({'text': 'I ate a banana'}),
            content_type='application/json',
            **self.headers
        )
        assert response.status_code == 503

    @patch('meals.services.meal_service.parse_meal')
    def test_text_success_creates_meal(self, mock_parse_meal):
        """Test successful text meal creation."""
        mock_parse_meal.return_value = [
            {
                'item_name': 'banana',
                'quantity': 1,
                'unit': 'piece',
                'calories': 89,
                'protein_g': 1.09,
                'carbs_g': 22.84,
                'fats_g': 0.33,
            }
        ]
        response = self.client.post(
            '/meals/text',
            data=json.dumps({'text': 'I ate a banana'}),
            content_type='application/json',
            **self.headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data['input_method'] == 'text'
        assert data['meal_items'][0]['item_name'] == 'banana'

    def test_image_no_file_provided(self):
        """Test image endpoint requires 'file' field."""
        response = self.client.post('/meals/image', {}, **self.headers)
        assert response.status_code == 400

    def test_image_unsupported_extension(self):
        """Test image endpoint rejects unsupported formats."""
        img = SimpleUploadedFile('photo.txt', b'not an image', content_type='text/plain')
        response = self.client.post('/meals/image', {'file': img}, **self.headers)
        assert response.status_code == 400

    def test_image_bad_magic_bytes_rejected(self):
        """Test image endpoint rejects files with wrong magic bytes."""
        # .jpg extension but content is not a valid JPEG
        img = SimpleUploadedFile('photo.jpg', b'not really a jpeg', content_type='image/jpeg')
        response = self.client.post('/meals/image', {'file': img}, **self.headers)
        assert response.status_code == 400

    @override_settings(MAX_IMAGE_SIZE_MB=0)
    def test_image_file_too_large(self):
        """Test image endpoint rejects files over size limit."""
        # Valid JPEG magic bytes but oversized
        img = SimpleUploadedFile('photo.jpg', b'\xff\xd8\xff' + b'x' * 100, content_type='image/jpeg')
        response = self.client.post('/meals/image', {'file': img}, **self.headers)
        assert response.status_code == 413

    @patch('meals.services.meal_service.parse_meal')
    @patch('meals.services.meal_service.scan_image')
    def test_image_no_items_identified_returns_422(self, mock_scan_image, mock_parse_meal):
        """Test image endpoint returns 422 when no items identified."""
        mock_scan_image.return_value = "a glass of water"
        mock_parse_meal.return_value = []
        img = SimpleUploadedFile('photo.jpg', b'\xff\xd8\xff' + b'fake jpeg', content_type='image/jpeg')
        response = self.client.post('/meals/image', {'file': img}, **self.headers)
        assert response.status_code == 422

    @patch('meals.services.meal_service.parse_meal')
    @patch('meals.services.meal_service.scan_image')
    def test_image_validation_error_returns_422(self, mock_scan_image, mock_parse_meal):
        """Test image endpoint returns 422 for non-transient vision errors (validation/auth)."""
        mock_scan_image.side_effect = ValueError("Could not extract any description from the photo")
        img = SimpleUploadedFile('photo.png', b'\x89PNG\r\n\x1a\n' + b'fake png', content_type='image/png')
        response = self.client.post('/meals/image', {'file': img}, **self.headers)
        assert response.status_code == 422
        data = response.json()
        assert "Could not extract" in data['detail']

    @patch('meals.services.meal_service.parse_meal')
    @patch('meals.services.meal_service.scan_image')
    def test_image_transient_error_returns_503(self, mock_scan_image, mock_parse_meal):
        """Test image endpoint returns 503 for transient vision service errors (capacity/rate limit)."""
        mock_scan_image.side_effect = LLMServiceError("Vision service is currently overloaded; please try again shortly")
        img = SimpleUploadedFile('photo.png', b'\x89PNG\r\n\x1a\n' + b'fake png', content_type='image/png')
        response = self.client.post('/meals/image', {'file': img}, **self.headers)
        assert response.status_code == 503
        data = response.json()
        assert "overloaded" in data['detail'].lower()

    @patch('meals.services.meal_service.parse_meal')
    @patch('meals.services.meal_service.scan_image')
    def test_image_success_creates_meal(self, mock_scan_image, mock_parse_meal):
        """Test successful image meal creation."""
        mock_scan_image.return_value = "a banana on a plate"
        mock_parse_meal.return_value = [
            {
                'item_name': 'banana',
                'quantity': 1,
                'unit': 'piece',
                'calories': 89,
                'protein_g': 1.09,
                'carbs_g': 22.84,
                'fats_g': 0.33,
            }
        ]
        img = SimpleUploadedFile('photo.jpg', b'\xff\xd8\xff' + b'fake jpeg', content_type='image/jpeg')
        response = self.client.post('/meals/image', {'file': img}, **self.headers)
        assert response.status_code == 201
        data = response.json()
        assert data['input_method'] == 'image'
        assert data['meal_items'][0]['item_name'] == 'banana'

    @patch('meals.services.food_lookup_service.lookup_ifct')
    @patch('meals.services.food_lookup_service.lookup_usda')
    @patch('meals.services.meal_service.transcribe')
    @patch('meals.services.meal_service.parse_meal')
    def test_voice_with_ifct_match(self, mock_parse, mock_transcribe, mock_usda, mock_ifct):
        """Voice meal with IFCT match — source should be 'ifct'."""
        mock_transcribe.return_value = "I had rice and daal"
        mock_parse.return_value = [
            {
                'item_name': 'rice',
                'quantity': 1,
                'unit': 'serving',
                'serving_size_grams': 100,
                'calories': 130,
                'protein_g': 2.7,
                'carbs_g': 28.0,
                'fats_g': 0.3,
                'fiber_g': 0.4,
                'confidence': 0.85,
            },
            {
                'item_name': 'daal',
                'quantity': 1,
                'unit': 'serving',
                'serving_size_grams': 100,
                'calories': 101,
                'protein_g': 9.0,
                'carbs_g': 18.0,
                'fats_g': 0.3,
                'fiber_g': 6.5,
                'confidence': 0.85,
            },
        ]

        mock_ifct.side_effect = [
            {
                'item_name': 'Rice, white, cooked',
                'calories_per_100g': 130,
                'protein_g_per_100g': 2.7,
                'carbs_g_per_100g': 28.0,
                'fats_g_per_100g': 0.3,
                'fiber_g_per_100g': 0.4,
                'source': 'ifct',
            },
            {
                'item_name': 'Daal (Red lentils), cooked',
                'calories_per_100g': 101,
                'protein_g_per_100g': 9.0,
                'carbs_g_per_100g': 18.0,
                'fats_g_per_100g': 0.3,
                'fiber_g_per_100g': 6.5,
                'source': 'ifct',
            },
        ]
        mock_usda.return_value = None

        audio = SimpleUploadedFile('voice.wav', b'RIFF' + b'\x00' * 96)
        response = self.client.post('/meals/voice', {'file': audio}, **self.headers)
        assert response.status_code == 201
        data = response.json()
        assert len(data['meal_items']) == 2
        assert data['meal_items'][0]['source'] == 'ifct'
        assert data['meal_items'][1]['source'] == 'ifct'

    @patch('meals.services.food_lookup_service.lookup_ifct')
    @patch('meals.services.food_lookup_service.lookup_usda')
    @patch('meals.services.meal_service.parse_meal')
    def test_text_with_usda_match(self, mock_parse, mock_usda, mock_ifct):
        """Text meal with USDA match (IFCT miss) — source should be 'usda_fdc'."""
        mock_parse.return_value = [
            {
                'item_name': 'banana',
                'quantity': 1,
                'unit': 'piece',
                'serving_size_grams': 100,
                'calories': 89,
                'protein_g': 1.09,
                'carbs_g': 23,
                'fats_g': 0.33,
                'fiber_g': 2.6,
                'confidence': 0.80,
            },
        ]

        mock_ifct.return_value = None
        mock_usda.return_value = {
            'item_name': 'Banana, raw',
            'calories_per_100g': 89,
            'protein_g_per_100g': 1.09,
            'carbs_g_per_100g': 23,
            'fats_g_per_100g': 0.33,
            'fiber_g_per_100g': 2.6,
            'source': 'usda_fdc',
        }

        response = self.client.post(
            '/meals/text',
            data=json.dumps({'text': 'I ate a banana'}),
            content_type='application/json',
            **self.headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data['meal_items'][0]['source'] == 'usda_fdc'

    @patch('meals.services.food_lookup_service.lookup_ifct')
    @patch('meals.services.food_lookup_service.lookup_usda')
    @patch('meals.services.meal_service.transcribe')
    @patch('meals.services.meal_service.parse_meal')
    def test_voice_with_llm_fallback(self, mock_parse, mock_transcribe, mock_usda, mock_ifct):
        """Both IFCT and USDA miss — keep LLM estimate, source='llm_estimate'."""
        mock_transcribe.return_value = "I had xyz food"
        mock_parse.return_value = [
            {
                'item_name': 'xyz_nonexistent_food',
                'quantity': 1,
                'unit': 'serving',
                'serving_size_grams': 100,
                'calories': 150,
                'protein_g': 5,
                'carbs_g': 25,
                'fats_g': 3,
                'fiber_g': 1,
                'confidence': 0.70,
            },
        ]

        mock_ifct.return_value = None
        mock_usda.return_value = None

        audio = SimpleUploadedFile('voice.wav', b'RIFF' + b'\x00' * 96)
        response = self.client.post('/meals/voice', {'file': audio}, **self.headers)
        assert response.status_code == 201
        data = response.json()
        assert data['meal_items'][0]['source'] == 'llm_estimate'

    @patch('meals.services.food_lookup_service.lookup_ifct')
    @patch('meals.services.food_lookup_service.lookup_usda')
    def test_patch_does_not_trigger_lookup(self, mock_usda, mock_ifct):
        """PATCH rescales when item name unchanged (no new lookup). Use convertible units so rescale works."""
        from meals.models import Meal, MealItem
        meal = Meal.objects.create(user=self.user, original_text="Original meal")
        # Create an initial item with convertible unit (g) so rescale can work
        MealItem.objects.create(
            meal=meal,
            item_name='rice',
            quantity=100,
            unit='g',
            calories=130,
            protein_g=2.7,
            carbs_g=28,
            fats_g=0.3,
            fiber_g=0.4,
        )

        # Edit: same name, just change quantity (rescale should work, no lookup triggered)
        updated_items = [
            {
                'item_name': 'rice',
                'quantity': 200,
                'unit': 'g',
                'calories': 260,
                'protein_g': 5.4,
                'carbs_g': 56,
                'fats_g': 0.6,
                'fiber_g': 0.8,
                'confidence': 0.85,
            }
        ]

        mock_ifct.return_value = None
        mock_usda.return_value = None

        response = self.client.patch(
            f'/meals/{meal.id}',
            data=json.dumps({'meal_items': updated_items}),
            content_type='application/json',
            **self.headers
        )
        assert response.status_code == 200
        # With same name and qty rescale on convertible unit, lookups should not be called
        mock_ifct.assert_not_called()
        mock_usda.assert_not_called()

        data = response.json()
        # Macros should be rescaled from original (100g→200g = 2x: 130→260 cal)
        assert abs(data['meal_items'][0]['calories'] - 260) < 1
