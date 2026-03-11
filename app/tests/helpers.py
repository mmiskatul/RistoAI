from __future__ import annotations

from fastapi.testclient import TestClient


def register_and_login(client: TestClient, owner_credentials: dict[str, str]) -> dict[str, str]:
    register_response = client.post("/api/v1/auth/restaurant/register", json=owner_credentials)
    register_code = register_response.json()["debug_verification_code"]
    verify_registration = client.post(
        "/api/v1/auth/restaurant/verify-registration",
        json={"email": owner_credentials["email"], "code": register_code},
    )
    assert verify_registration.status_code == 200

    login_response = client.post(
        "/api/v1/auth/restaurant/login",
        json={"email": owner_credentials["email"], "password": owner_credentials["password"]},
    )
    tokens = login_response.json()["tokens"]
    return {"Authorization": f"Bearer {tokens['access_token']}"}
