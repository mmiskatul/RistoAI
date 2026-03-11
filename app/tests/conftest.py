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
        "full_name": "Risto Owner",
        "email": "owner@example.com",
        "password": "OwnerPass123",
        "phone": "+15550001111",
    }


def register_and_login(client: TestClient, owner_credentials: dict[str, str]) -> dict[str, str]:
    client.post("/api/v1/auth/register", json=owner_credentials)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": owner_credentials["email"], "password": owner_credentials["password"]},
    )
    tokens = response.json()["tokens"]
    return {"Authorization": f"Bearer {tokens['access_token']}"}
