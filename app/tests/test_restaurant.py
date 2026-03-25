from __future__ import annotations

from datetime import UTC, datetime

from app.tests.helpers import register_and_login, seed_subscription_plan, select_subscription_plan


def test_restaurant_document_upload_extract_and_confirm_flow(client, app):
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
    assert upload_response.status_code == 200
    upload_payload = upload_response.json()
    assert upload_payload["supplier_name"] == "Fresh Food Supplier Ltd"
    assert upload_payload["ai_provider"] == "fallback"
    assert upload_payload["invoice_date"] is None
    assert len(upload_payload["line_items"]) == 3
    assert "id" not in upload_payload

    pre_confirm_list_response = client.get("/api/v1/restaurant/documents", headers=headers)
    assert pre_confirm_list_response.status_code == 200
    assert pre_confirm_list_response.json()["total"] == 0

    confirm_response = client.post(
        "/api/v1/restaurant/documents/confirm-save",
        headers=headers,
        json={
            "supplier_name": "Bakery Goods Co",
            "invoice_number": upload_payload["invoice_number"],
            "total_amount": 425.0,
            "line_items": [
                {"product_name": "Sourdough Loaf", "quantity": 20, "unit_price": 5.0, "total_price": 100.0},
                {"product_name": "Pastry Flour (25kg)", "quantity": 5, "unit_price": 45.0, "total_price": 225.0},
                {"product_name": "Butter (Case)", "quantity": 2, "unit_price": 50.0, "total_price": 100.0}
            ],
            "source_file_name": upload_payload["source_file_name"],
            "ai_provider": upload_payload["ai_provider"],
            "ai_summary": upload_payload["ai_summary"]
        },
    )
    assert confirm_response.status_code == 201
    assert confirm_response.json()["status"] == "processed"
    assert confirm_response.json()["supplier_name"] == "Bakery Goods Co"
    assert confirm_response.json()["confirmed_by_user_id"]
    assert confirm_response.json()["confirmed_at"]
    assert confirm_response.json()["invoice_date"] == datetime.now(UTC).date().isoformat()

    document_id = confirm_response.json()["id"]
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

    today_iso = datetime.now(UTC).date().isoformat()
    date_data_response = client.get(f"/api/v1/restaurant/daily-data?view=date&reference_date={today_iso}", headers=headers)
    assert date_data_response.status_code == 200
    date_payload = date_data_response.json()
    assert date_payload["summary_cards"][1]["label"] == "Total Expenses"
    assert date_payload["summary_cards"][1]["value"] == 425.0
    assert date_payload["items"][0]["business_date"] == today_iso
    assert date_payload["items"][0]["total_expenses"] == 425.0
    assert date_payload["items"][0]["total_expenses_formatted"] == "$425.00"
    assert date_payload["items"][0]["actions"]["view_endpoint"] is None
    assert date_payload["items"][0]["data_sources"][0]["kind"] == "uploaded_invoice"
    assert date_payload["items"][0]["data_sources"][0]["label"] == "Uploaded invoices"
    assert date_payload["items"][0]["data_sources"][0]["count"] == 1

    week_data_response = client.get(f"/api/v1/restaurant/daily-data?view=week&reference_date={today_iso}", headers=headers)
    assert week_data_response.status_code == 200
    assert week_data_response.json()["summary_cards"][1]["label"] == "This Week Expenses"
    assert week_data_response.json()["summary_cards"][1]["value"] == 425.0

    month_data_response = client.get(f"/api/v1/restaurant/daily-data?view=month&reference_date={today_iso}", headers=headers)
    assert month_data_response.status_code == 200
    assert month_data_response.json()["summary_cards"][1]["label"] == "This Month Expenses"
    assert month_data_response.json()["summary_cards"][1]["value"] == 425.0


def test_restaurant_endpoints_are_scoped_per_user(client, app):
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


def test_restaurant_daily_data_dashboard_analytics_and_chat(client, app):
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

    second_daily_response = client.post(
        "/api/v1/restaurant/daily-data",
        headers=headers,
        json={
            "method": "method_2",
            "method_two": {
                "business_date": "2026-03-25",
                "pos_payments": 600,
                "cash_payments": 200,
                "bank_transfer_payments": 120,
                "lunch_covers": 20,
                "dinner_covers": 18,
                "opening_cash": 100,
                "closing_cash": 220,
            },
        },
    )
    assert second_daily_response.status_code == 201

    daily_list_response = client.get("/api/v1/restaurant/daily-data?view=date&reference_date=2026-03-26", headers=headers)
    assert daily_list_response.status_code == 200
    daily_list_payload = daily_list_response.json()
    assert daily_list_payload["page_title"] == "Daily Data Management"
    assert daily_list_payload["subtitle"] == "Track and manage your restaurant performance"
    assert daily_list_payload["view_options"] == ["date", "week", "month"]
    assert daily_list_payload["active_view"] == "date"
    assert len(daily_list_payload["summary_cards"]) == 5
    assert daily_list_payload["summary_cards"][0]["label"] == "Today's Revenue"
    assert daily_list_payload["summary_cards"][0]["value"] == 920
    assert daily_list_payload["summary_cards"][0]["value_formatted"] == "$920.00"
    assert daily_list_payload["summary_cards"][0]["icon_key"] == "revenue"
    assert daily_list_payload["summary_cards"][3]["label"] == "Total Covers"
    assert daily_list_payload["summary_cards"][3]["value"] == 38
    assert daily_list_payload["add_button"]["label"] == "Add Daily Data"
    assert daily_list_payload["add_button"]["endpoint"] == "/api/v1/restaurant/daily-data"
    assert daily_list_payload["items"][0]["business_date"] == "2026-03-25"
    assert daily_list_payload["items"][0]["business_date_formatted"] == "Mar 25, 2026"
    assert daily_list_payload["items"][0]["day_label"] == "YESTERDAY"
    assert daily_list_payload["items"][0]["total_covers"] == 38
    assert daily_list_payload["items"][0]["total_expenses"] == 0.0
    assert daily_list_payload["items"][0]["total_revenue_formatted"] == "$920.00"
    assert daily_list_payload["items"][0]["avg_revenue_per_cover"] == 24.21
    assert daily_list_payload["items"][0]["avg_revenue_per_cover_formatted"] == "$24.21"
    assert daily_list_payload["items"][0]["data_sources"][0]["kind"] == "daily_record"
    assert daily_list_payload["items"][0]["actions"]["view_endpoint"].endswith(daily_list_payload["items"][0]["id"])
    assert daily_list_payload["items"][0]["actions"]["delete_endpoint"].endswith(daily_list_payload["items"][0]["id"])

    week_list_response = client.get("/api/v1/restaurant/daily-data?view=week&reference_date=2026-03-26", headers=headers)
    assert week_list_response.status_code == 200
    week_payload = week_list_response.json()
    assert week_payload["active_view"] == "week"
    assert week_payload["summary_cards"][0]["label"] == "This Week Revenue"
    assert week_payload["total"] == 2

    detail_id = daily_list_payload["items"][0]["id"]
    detail_response = client.get(f"/api/v1/restaurant/daily-data/{detail_id}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["business_date"] == "2026-03-25"

    month_list_response = client.get("/api/v1/restaurant/daily-data?view=month&reference_date=2026-03-26", headers=headers)
    assert month_list_response.status_code == 200
    month_payload = month_list_response.json()
    assert month_payload["active_view"] == "month"
    assert month_payload["summary_cards"][0]["label"] == "This Month Revenue"
    assert month_payload["total"] == 2

    delete_response = client.delete(f"/api/v1/restaurant/daily-data/{detail_id}", headers=headers)
    assert delete_response.status_code == 204
    after_delete_response = client.get("/api/v1/restaurant/daily-data?view=date&reference_date=2026-03-26", headers=headers)
    assert after_delete_response.status_code == 200
    assert after_delete_response.json()["total"] == 1

    analytics_response = client.get("/api/v1/restaurant/analytics/overview", headers=headers)
    assert analytics_response.status_code == 200
    assert analytics_response.json()["revenue_total"] == 1300

    chat_response = client.post("/api/v1/restaurant/chat/messages", headers=headers, json={"message": "How can I improve profit?"})
    assert chat_response.status_code == 201
    messages = chat_response.json()["messages"]
    assert messages[-1]["role"] == "assistant"
    assert "revenue" in messages[-1]["message"].lower()


