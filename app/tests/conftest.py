from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from app.db.mongodb import get_database
from app.main import create_app


@pytest.fixture()
def app():
    application = create_app(testing=True)
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client["ristoai_test"]

    async def override_get_database():
        return mock_db

    application.dependency_overrides[get_database] = override_get_database
    return application


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def owner_credentials() -> dict[str, str]:
    return {
        "full_name": "Masab Miskat",
        "email": "masabimiskat@gmail.com",
        "password": "password123",
        "phone": "+15550001111",
    }
