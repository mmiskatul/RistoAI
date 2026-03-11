from __future__ import annotations

from app.tests.conftest import register_and_login


def test_order_creation_calculates_totals_in_backend(client, owner_credentials):
    headers = register_and_login(client, owner_credentials)
    restaurant = client.post(
        "/api/v1/restaurants",
        headers=headers,
        json={
            "name": "Orders Lab",
            "description": "Restaurant for order tests",
            "cuisine_type": "Asian",
            "contact_email": "orders@lab.com",
            "contact_phone": "+15550004444",
            "address": "789 Service Road",
            "settings": {"tax_rate": 0.1},
        },
    ).json()
    branch = client.post(
        "/api/v1/branches",
        headers=headers,
        json={
            "restaurant_id": restaurant["id"],
            "name": "Downtown",
            "address": "789 Service Road",
            "phone": "+15550005555",
            "manager_ids": [],
        },
    ).json()
    category = client.post(
        "/api/v1/menu-categories",
        headers=headers,
        json={
            "restaurant_id": restaurant["id"],
            "name": "Bowls",
            "description": "Rice bowls",
            "sort_order": 1,
        },
    ).json()
    item = client.post(
        "/api/v1/menu-items",
        headers=headers,
        json={
            "restaurant_id": restaurant["id"],
            "branch_id": branch["id"],
            "category_id": category["id"],
            "name": "Chicken Bowl",
            "description": "Hot bowl",
            "price": 12.0,
            "availability": True,
            "preparation_time": 12,
            "tags": ["bowl"],
        },
    ).json()

    order_response = client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "restaurant_id": restaurant["id"],
            "branch_id": branch["id"],
            "items": [{"menu_item_id": item["id"], "quantity": 2}],
            "discount": 1.0,
            "payment_status": "pending",
        },
    )
    assert order_response.status_code == 201
    payload = order_response.json()
    assert payload["subtotal"] == 24.0
    assert payload["tax"] == 2.4
    assert payload["total"] == 25.4
