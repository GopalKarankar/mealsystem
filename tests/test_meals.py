import pytest
import json
from datetime import datetime, timedelta
from django.test import Client
from django.utils import timezone
from accounts.models import User
from meals.models import Meal, MealItem
from accounts.jwt import create_access_token


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

        # Create meal for today
        meal_today = Meal.objects.create(
            user=self.user,
            original_text="Today meal",
            transcription_text="Today meal",
            confidence_score=0.85,
            created_at=timezone.make_aware(datetime.combine(today, datetime.min.time())),
        )

        # Create meal for yesterday
        yesterday = today - timedelta(days=1)
        meal_yesterday = Meal.objects.create(
            user=self.user,
            original_text="Yesterday meal",
            transcription_text="Yesterday meal",
            confidence_score=0.85,
            created_at=timezone.make_aware(datetime.combine(yesterday, datetime.min.time())),
        )

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
        response = self.client.get('/dashboard', **self.headers)
        assert response.status_code == 400

    def test_dashboard_with_valid_date(self):
        """Test dashboard returns totals and meals."""
        today = timezone.now().date()
        date_str = today.strftime("%Y-%m-%d")

        # Create meal
        meal = Meal.objects.create(
            user=self.user,
            original_text="Test meal",
            transcription_text="Test meal",
            confidence_score=0.85,
            created_at=timezone.make_aware(datetime.combine(today, datetime.min.time())),
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

        response = self.client.get(f'/dashboard?date={date_str}', **self.headers)
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
                    'unit': 'medium',
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
                    'unit': 'medium',
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
                        'unit': 'medium',
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
