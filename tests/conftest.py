import pytest
from accounts.models import User


@pytest.fixture
def test_user(db):
    """Fixture for a test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def test_user_with_google(db):
    """Fixture for a test user with Google OAuth."""
    return User.objects.create_user(
        username='googletestuser',
        email='google@example.com',
        password=None,
        google_id='google_123456'
    )
