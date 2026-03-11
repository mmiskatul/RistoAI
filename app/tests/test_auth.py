from __future__ import annotations

from app.tests.conftest import register_and_login


def test_auth_register_login_and_me(client, owner_credentials):
    register_response = client.post("/api/v1/auth/register", json=owner_credentials)
    assert register_response.status_code == 201
    assert register_response.json()["user"]["email"] == owner_credentials["email"]

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": owner_credentials["email"], "password": owner_credentials["password"]},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["tokens"]["access_token"]

    me_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_response.status_code == 200
    assert me_response.json()["role"] == "restaurant_owner"
