from __future__ import annotations

from app.tests.conftest import register_and_login


def test_menu_item_creation(client, owner_credentials):
    headers = register_and_login(client, owner_credentials)
    restaurant = client.post(
        "/api/v1/restaurants",
        headers=headers,
        json={
            "name": "Menu Hub",
            "description": "Restaurant for menu tests",
            "cuisine_type": "Fusion",
            "contact_email": "menu@hub.com",
            "contact_phone": "+15550003333",
            "address": "456 Flavor Avenue",
            "settings": {"tax_rate": 0.1},
        },
    ).json()

    category = client.post(
        "/api/v1/menu-categories",
        headers=headers,
        json={
            "restaurant_id": restaurant["id"],
            "name": "Mains",
            "description": "Core dishes",
            "sort_order": 1,
        },
    ).json()

    item_response = client.post(
        "/api/v1/menu-items",
        headers=headers,
        json={
            "restaurant_id": restaurant["id"],
            "category_id": category["id"],
            "name": "Smoked Pasta",
            "description": "Creamy signature pasta",
            "price": 18.5,
            "availability": True,
            "preparation_time": 15,
            "tags": ["Signature", "Pasta"],
        },
    )
    assert item_response.status_code == 201
    assert item_response.json()["name"] == "Smoked Pasta"
    assert item_response.json()["tags"] == ["pasta", "signature"]
