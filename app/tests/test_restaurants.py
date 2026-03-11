from __future__ import annotations

from app.tests.conftest import register_and_login


def test_restaurant_creation(client, owner_credentials):
    headers = register_and_login(client, owner_credentials)
    response = client.post(
        "/api/v1/restaurants",
        headers=headers,
        json={
            "name": "Risto Prime",
            "description": "Flagship location",
            "cuisine_type": "Italian",
            "contact_email": "hello@ristoprime.com",
            "contact_phone": "+15550002222",
            "address": "123 Main Street",
            "settings": {"tax_rate": 0.1},
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Risto Prime"
    assert payload["contact_email"] == "hello@ristoprime.com"
