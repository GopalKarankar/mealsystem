import pytest
from pymongo import MongoClient
from app.config import settings


@pytest.fixture(scope="function")
def db():
    """Fixture for test database."""
    client = MongoClient(settings.mongodb_url)
    test_db = client[f"{settings.mongodb_db_name}_test"]

    yield test_db

    test_db.foods.delete_many({})
    test_db.meals.delete_many({})
    client.close()
