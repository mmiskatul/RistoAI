from __future__ import annotations

from app.tests.helpers import register_and_login, seed_subscription_plan, select_subscription_plan


def test_mobile_document_upload_extract_and_confirm_flow(client, app):
    seed_subscription_plan(app)
    headers = register_and_login(
        client,
        {
            "full_name": "Marco Owner",
            "email": "marco@example.com",
            "password": "MarcoPass123",
            "phone": "+3900000001",
        },
    )
    select_subscription_plan(client, headers)

    upload_response = client.post(
        "/api/v1/restaurant/documents/upload-extract",
        headers=headers,
        files={"file": ("invoice-march.png", b"fake-image", "image/png")},
    )
    assert upload_response.status_code == 201
    upload_payload = upload_response.json()
    assert upload_payload["supplier_name"] == "Fresh Food Supplier Ltd"
    assert upload_payload["status"] == "pending_review"
    assert upload_payload["ai_provider"] == "fallback"
    assert len(upload_payload["line_items"]) == 3

    document_id = upload_payload["id"]

    edit_response = client.patch(
        f"/api/v1/restaurant/documents/{document_id}",
        headers=headers,
        json={
            "supplier_name": "Bakery Goods Co",
            "invoice_date": "2026-03-10",
            "line_items": [
                {"product_name": "Sourdough Loaf", "quantity": 20, "unit_price": 5.0, "total_price": 100.0},
                {"product_name": "Pastry Flour (25kg)", "quantity": 5, "unit_price": 45.0, "total_price": 225.0},
                {"product_name": "Butter (Case)", "quantity": 2, "unit_price": 50.0, "total_price": 100.0}
            ],
            "total_amount": 425.0,
        },
    )
    assert edit_response.status_code == 200
    assert edit_response.json()["status"] == "pending_review"
    assert edit_response.json()["supplier_name"] == "Bakery Goods Co"
    assert edit_response.json()["last_edited_by_user_id"]

    confirm_response = client.post(
        f"/api/v1/restaurant/documents/{document_id}/confirm",
        headers=headers,
        json={"supplier_name": "Bakery Goods Co", "total_amount": 425.0},
    )
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "processed"
    assert confirm_response.json()["supplier_name"] == "Bakery Goods Co"
    assert confirm_response.json()["confirmed_by_user_id"]
    assert confirm_response.json()["confirmed_at"]
    assert confirm_response.json()["invoice_date"] == "2026-03-10"

    list_response = client.get("/api/v1/restaurant/documents", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert list_response.json()["items"][0]["source_file_name"] == "invoice-march.png"
    assert list_response.json()["items"][0]["confirmed_at"]

    detail_response = client.get(f"/api/v1/restaurant/documents/{document_id}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["created_by_user_id"]
    assert detail_response.json()["last_edited_by_user_id"]
    assert detail_response.json()["confirmed_by_user_id"]


def test_mobile_endpoints_are_scoped_per_user(client, app):
    seed_subscription_plan(app)
    headers_user_one = register_and_login(
        client,
        {
            "full_name": "Owner One",
            "email": "owner1@example.com",
            "password": "OwnerOne123",
            "phone": "+1555000001",
        },
    )
    select_subscription_plan(client, headers_user_one)

    headers_user_two = register_and_login(
        client,
        {
            "full_name": "Owner Two",
            "email": "owner2@example.com",
            "password": "OwnerTwo123",
            "phone": "+1555000002",
        },
    )
    select_subscription_plan(client, headers_user_two)

    expense_response = client.post(
        "/api/v1/restaurant/expenses",
        headers=headers_user_one,
        json={"category": "Staff Costs", "amount": 420.0, "expense_date": "2026-03-20", "notes": "Payroll"},
    )
    assert expense_response.status_code == 201

    inventory_response = client.post(
        "/api/v1/restaurant/inventory",
        headers=headers_user_one,
        json={
            "product_name": "Tomato Sauce",
            "category": "Sauce",
            "stock_quantity": 12,
            "unit_type": "bottles",
            "supplier_name": "Global Foods Inc.",
            "unit_price": 4.5,
            "alert_threshold": 5,
            "purchase_date": "2026-03-10",
        },
    )
    assert inventory_response.status_code == 201
    inventory_id = inventory_response.json()["id"]

    expenses_user_two = client.get("/api/v1/restaurant/expenses", headers=headers_user_two)
    assert expenses_user_two.status_code == 200
    assert expenses_user_two.json()["total"] == 0

    inventory_user_two = client.get("/api/v1/restaurant/inventory", headers=headers_user_two)
    assert inventory_user_two.status_code == 200
    assert inventory_user_two.json()["total"] == 0

    inventory_detail_user_two = client.get(f"/api/v1/restaurant/inventory/{inventory_id}", headers=headers_user_two)
    assert inventory_detail_user_two.status_code == 404


def test_mobile_daily_data_dashboard_analytics_and_chat(client, app):
    seed_subscription_plan(app)
    headers = register_and_login(
        client,
        {
            "full_name": "Alex Chef",
            "email": "alex@example.com",
            "password": "AlexChef123",
            "phone": "+1555000003",
        },
    )
    select_subscription_plan(client, headers)

    create_daily_response = client.post(
        "/api/v1/restaurant/daily-data",
        headers=headers,
        json={
            "method": "method_2",
            "method_two": {
                "business_date": "2026-03-24",
                "pos_payments": 800,
                "cash_payments": 300,
                "bank_transfer_payments": 200,
                "lunch_covers": 45,
                "dinner_covers": 60,
                "opening_cash": 150,
                "closing_cash": 420,
            },
        },
    )
    assert create_daily_response.status_code == 201
    assert create_daily_response.json()["profit"] == 1300

    client.post(
        "/api/v1/restaurant/expenses",
        headers=headers,
        json={"category": "Food Supplies", "amount": 250.0, "expense_date": "2026-03-24"},
    )

    home_response = client.get("/api/v1/restaurant/home", headers=headers)
    assert home_response.status_code == 200
    assert home_response.json()["metrics"][0]["label"] == "Revenue"

    insights_response = client.get("/api/v1/restaurant/insights", headers=headers)
    assert insights_response.status_code == 200
    assert insights_response.json()["page_title"] == "AI Business Insights"
    assert len(insights_response.json()["root_causes"]) == 3
    assert len(insights_response.json()["recommended_actions"]) == 3
    assert insights_response.json()["export_label"] == "Export"

    analytics_response = client.get("/api/v1/restaurant/analytics/overview", headers=headers)
    assert analytics_response.status_code == 200
    assert analytics_response.json()["revenue_total"] == 1300

    chat_response = client.post("/api/v1/restaurant/chat/messages", headers=headers, json={"message": "How can I improve profit?"})
    assert chat_response.status_code == 201
    messages = chat_response.json()["messages"]
    assert messages[-1]["role"] == "assistant"
    assert "revenue" in messages[-1]["message"].lower()


