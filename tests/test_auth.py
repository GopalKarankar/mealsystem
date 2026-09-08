import pytest
import json
from django.test import Client
from accounts.models import User


@pytest.mark.django_db
class TestRegisterEndpoint:
    def setup_method(self):
        self.client = Client()

    def test_register_success(self):
        """Test successful user registration."""
        response = self.client.post(
            '/auth/register',
            data=json.dumps({
                'username': 'newuser',
                'email': 'new@example.com',
                'password': 'securepass123'
            }),
            content_type='application/json'
        )

        assert response.status_code == 201
        data = response.json()
        assert 'access_token' in data
        assert data['token_type'] == 'bearer'
        assert 'user_id' in data
        assert data['expires_in'] == 604800  # 7 days

        # Verify user was created
        user = User.objects.get(email='new@example.com')
        assert user.username == 'newuser'

    def test_register_username_taken(self):
        """Test registration fails when username is taken."""
        # Create existing user
        User.objects.create_user(username='existinguser', email='existing@example.com', password='pass123')

        response = self.client.post(
            '/auth/register',
            data=json.dumps({
                'username': 'existinguser',
                'email': 'different@example.com',
                'password': 'securepass123'
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.json()
        assert 'detail' in data

    def test_register_email_taken(self):
        """Test registration fails when email is taken."""
        User.objects.create_user(username='existinguser', email='existing@example.com', password='pass123')

        response = self.client.post(
            '/auth/register',
            data=json.dumps({
                'username': 'newuser',
                'email': 'existing@example.com',
                'password': 'securepass123'
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.json()
        assert 'detail' in data

    def test_register_invalid_username_format(self):
        """Test registration fails with invalid username format."""
        response = self.client.post(
            '/auth/register',
            data=json.dumps({
                'username': 'user@invalid',  # @ is not allowed
                'email': 'new@example.com',
                'password': 'securepass123'
            }),
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_register_short_password(self):
        """Test registration fails with short password."""
        response = self.client.post(
            '/auth/register',
            data=json.dumps({
                'username': 'newuser',
                'email': 'new@example.com',
                'password': 'short'
            }),
            content_type='application/json'
        )

        assert response.status_code == 400


@pytest.mark.django_db
class TestLoginEndpoint:
    def setup_method(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_login_success(self):
        """Test successful login."""
        response = self.client.post(
            '/auth/login',
            data=json.dumps({
                'email': 'test@example.com',
                'password': 'testpass123'
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert 'access_token' in data
        assert data['token_type'] == 'bearer'
        assert data['user_id'] == str(self.user.id)
        assert data['expires_in'] == 604800

    def test_login_invalid_password(self):
        """Test login fails with invalid password."""
        response = self.client.post(
            '/auth/login',
            data=json.dumps({
                'email': 'test@example.com',
                'password': 'wrongpassword'
            }),
            content_type='application/json'
        )

        assert response.status_code == 401
        data = response.json()
        assert 'detail' in data

    def test_login_user_not_found(self):
        """Test login fails when user doesn't exist."""
        response = self.client.post(
            '/auth/login',
            data=json.dumps({
                'email': 'notfound@example.com',
                'password': 'anypassword'
            }),
            content_type='application/json'
        )

        assert response.status_code == 401
        data = response.json()
        assert 'detail' in data


@pytest.mark.django_db
class TestGoogleLoginEndpoint:
    def setup_method(self):
        self.client = Client()

    def test_google_login_not_configured(self):
        """Test Google login returns error when not configured."""
        # GOOGLE_CLIENT_ID is empty by default in test
        response = self.client.post(
            '/auth/google',
            data=json.dumps({
                'id_token': 'fake-token'
            }),
            content_type='application/json'
        )

        # Will fail because GOOGLE_CLIENT_ID is empty
        assert response.status_code in [401, 500]
