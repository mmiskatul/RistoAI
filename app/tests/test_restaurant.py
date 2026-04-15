from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from bson import ObjectId

from app.db.migrations import MIGRATION_KEY, run_data_migrations
from app.db.mongodb import get_database
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
    assert set(upload_payload.keys()) == {
        "document_type",
        "document_label",
        "counterparty_name",
        "document_number",
        "document_date",
        "total_amount",
        "currency",
        "expense_amount",
        "cash_amount",
        "revenue_amount",
        "profit_amount",
        "line_items",
        "source_file_name",
        "ai_provider",
        "ai_summary",
    }
    assert upload_payload["document_type"] == "expense"
    assert upload_payload["document_label"] == "Expense"
    assert upload_payload["counterparty_name"] == "Fresh Food Supplier Ltd"
    assert upload_payload["ai_provider"] == "fallback"
    assert upload_payload["document_date"] == "2026-03-10"
    assert upload_payload["total_amount"] == 165.0
    assert upload_payload["currency"] == "EUR"
    assert upload_payload["expense_amount"] == 165.0
    assert upload_payload["cash_amount"] == 0.0
    assert upload_payload["revenue_amount"] == 0.0
    assert upload_payload["profit_amount"] == 0.0
    assert len(upload_payload["line_items"]) == 3
    assert "id" not in upload_payload

    confirm_response = client.post(
        "/api/v1/restaurant/documents/confirm-save",
        headers=headers,
        json={
            "document_type": upload_payload["document_type"],
            "document_label": upload_payload["document_label"],
            "counterparty_name": upload_payload["counterparty_name"],
            "supplier_name": "Bakery Goods Co",
            "invoice_number": upload_payload["document_number"],
            "total_amount": 425.0,
            "currency": upload_payload["currency"],
            "expense_amount": 425.0,
            "cash_amount": 0.0,
            "revenue_amount": 0.0,
            "profit_amount": 0.0,
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
    assert confirm_response.json()["document_type"] == "expense"
    assert confirm_response.json()["document_label"] == "Expense"
    assert confirm_response.json()["counterparty_name"] == "Fresh Food Supplier Ltd"
    assert confirm_response.json()["currency"] == "EUR"
    assert confirm_response.json()["expense_amount"] == 425.0
    assert confirm_response.json()["cash_amount"] == 0.0
    assert confirm_response.json()["revenue_amount"] == 0.0
    assert confirm_response.json()["profit_amount"] == 0.0
    assert confirm_response.json()["confirmed_by_user_id"]
    assert confirm_response.json()["confirmed_at"]
    assert confirm_response.json()["document_date"] == datetime.now(UTC).date().isoformat()
    assert "page_title" not in confirm_response.json()
    assert confirm_response.json()["status"] == "processed"
    assert confirm_response.json()["line_items"][0]["product_name"] == "Sourdough Loaf"

    assert confirm_response.json()["created_by_user_id"]
    assert confirm_response.json()["last_edited_by_user_id"]
    assert confirm_response.json()["confirmed_by_user_id"]

    documents_response = client.get("/api/v1/restaurant/documents", headers=headers)
    assert documents_response.status_code == 200
    documents_payload = documents_response.json()
    assert set(documents_payload.keys()) == {"total", "page", "page_size", "pages", "items"}
    assert documents_payload["items"][0]["document_type"] == "expense"
    assert documents_payload["items"][0]["counterparty_name"] == "Fresh Food Supplier Ltd"
    assert documents_payload["items"][0]["status"] == "processed"
    assert documents_payload["items"][0]["line_item_count"] == 3

    today_iso = datetime.now(UTC).date().isoformat()
    document_detail_response = client.get(f"/api/v1/restaurant/documents/{confirm_response.json()['id']}", headers=headers)
    assert document_detail_response.status_code == 200
    document_detail_payload = document_detail_response.json()
    assert document_detail_payload["document_type"] == "expense"
    assert document_detail_payload["document_label"] == "Expense"
    assert document_detail_payload["counterparty_name"] == "Fresh Food Supplier Ltd"
    assert document_detail_payload["document_date"] == today_iso
    assert document_detail_payload["upload_date"]
    assert document_detail_payload["expense_amount"] == 425.0
    assert "page_title" not in document_detail_payload
    assert "source_file_name" not in document_detail_payload

    download_response = client.get(f"/api/v1/restaurant/documents/{confirm_response.json()['id']}/download", headers=headers)
    assert download_response.status_code == 200
    assert download_response.headers["content-type"].startswith("application/pdf")
    assert "attachment; filename=" in download_response.headers["content-disposition"]
    assert download_response.content.startswith(b"%PDF")

    download_svg_response = client.get(f"/api/v1/restaurant/documents/{confirm_response.json()['id']}/download-image?format=svg", headers=headers)
    assert download_svg_response.status_code == 200
    assert download_svg_response.headers["content-type"].startswith("image/svg+xml")
    assert "attachment; filename=" in download_svg_response.headers["content-disposition"]
    assert b"<svg" in download_svg_response.content

    date_data_response = client.get(f"/api/v1/restaurant/daily-data?view=date&reference_date={today_iso}", headers=headers)
    assert date_data_response.status_code == 200
    date_payload = date_data_response.json()
    assert set(date_payload.keys()) == {"total", "page", "page_size", "pages", "items"}
    assert date_payload["items"][0]["business_date"] == today_iso
    assert date_payload["items"][0]["total_expenses"] == 425.0
    assert date_payload["items"][0]["total_revenue"] == 0.0

    week_data_response = client.get(f"/api/v1/restaurant/daily-data?view=week&reference_date={today_iso}", headers=headers)
    assert week_data_response.status_code == 200
    assert set(week_data_response.json().keys()) == {"total", "page", "page_size", "pages", "items"}

    invoice_detail_response = client.get(f"/api/v1/restaurant/daily-data/by-date?business_date={today_iso}", headers=headers)
    assert invoice_detail_response.status_code == 200
    invoice_detail_payload = invoice_detail_response.json()
    assert invoice_detail_payload["business_date"] == today_iso
    assert invoice_detail_payload["total_revenue"] == 0.0
    assert invoice_detail_payload["total_expenses"] == 425.0
    assert invoice_detail_payload["total_covers"] == 0
    assert invoice_detail_payload["document_count"] == 1
    assert invoice_detail_payload["documents"][0]["counterparty_name"] == "Fresh Food Supplier Ltd"
    assert invoice_detail_payload["documents"][0]["total_amount"] == 425.0

    week_invoice_detail_response = client.get(f"/api/v1/restaurant/daily-data/by-week?reference_date={today_iso}", headers=headers)
    assert week_invoice_detail_response.status_code == 200
    week_invoice_detail_payload = week_invoice_detail_response.json()
    assert week_invoice_detail_payload["business_date"] == today_iso
    assert week_invoice_detail_payload["total_expenses"] == 425.0
    assert week_invoice_detail_payload["document_count"] == 1
    assert week_invoice_detail_payload["documents"][0]["counterparty_name"] == "Fresh Food Supplier Ltd"

    month_invoice_detail_response = client.get(f"/api/v1/restaurant/daily-data/by-month?reference_date={today_iso}", headers=headers)
    assert month_invoice_detail_response.status_code == 200
    month_invoice_detail_payload = month_invoice_detail_response.json()
    assert month_invoice_detail_payload["business_date"] == today_iso
    assert month_invoice_detail_payload["total_expenses"] == 425.0
    assert month_invoice_detail_payload["document_count"] == 1
    assert month_invoice_detail_payload["documents"][0]["counterparty_name"] == "Fresh Food Supplier Ltd"

    date_reference_detail_response = client.get(f"/api/v1/restaurant/daily-data/by-date-reference?reference_date={today_iso}", headers=headers)
    assert date_reference_detail_response.status_code == 200
    assert date_reference_detail_response.json()["business_date"] == today_iso

    week_business_date_detail_response = client.get(f"/api/v1/restaurant/daily-data/by-week-business-date?business_date={today_iso}", headers=headers)
    assert week_business_date_detail_response.status_code == 200
    assert week_business_date_detail_response.json()["business_date"] == today_iso
    assert week_business_date_detail_response.json()["document_count"] == 1

    month_business_date_detail_response = client.get(f"/api/v1/restaurant/daily-data/by-month-business-date?business_date={today_iso}", headers=headers)
    assert month_business_date_detail_response.status_code == 200
    assert month_business_date_detail_response.json()["business_date"] == today_iso
    assert month_business_date_detail_response.json()["document_count"] == 1

    all_dates_response = client.get("/api/v1/restaurant/daily-data/by-date", headers=headers)
    assert all_dates_response.status_code == 200
    assert all_dates_response.json()["total"] >= 1
    assert all_dates_response.json()["items"][0]["business_date"]

    all_weeks_response = client.get("/api/v1/restaurant/daily-data/by-week", headers=headers)
    assert all_weeks_response.status_code == 200
    assert all_weeks_response.json()["total"] >= 1
    assert all_weeks_response.json()["items"][0]["business_date"]

    all_months_response = client.get("/api/v1/restaurant/daily-data/by-month", headers=headers)
    assert all_months_response.status_code == 200
    assert all_months_response.json()["total"] >= 1
    assert all_months_response.json()["items"][0]["business_date"]
    manual_entry_response = client.post(
        "/api/v1/restaurant/manual-entry",
        headers=headers,
        json={
            "method": "method_2",
            "method_two": {
                "business_date": today_iso,
                "pos_payments": 800,
                "cash_payments": 200,
                "bank_transfer_payments": 100,
                "lunch_covers": 10,
                "dinner_covers": 12,
                "opening_cash": 100,
                "closing_cash": 180
            }
        },
    )
    assert manual_entry_response.status_code == 201

    db = asyncio.run(app.dependency_overrides[get_database]())
    restaurant_record = asyncio.run(
        db["restaurant_finance_snapshots"].find_one(
            {
                "period_type": "day",
                "business_date": datetime.now(UTC).date().isoformat(),
                "uploaded_document_ids": {"$in": [confirm_response.json()["id"]]},
            }
        )
    )
    assert restaurant_record is not None
    assert restaurant_record["uploaded_document_count"] == 1
    assert restaurant_record["manual_entry_id"] is not None
    assert restaurant_record["total_revenue"] == 1100.0
    assert restaurant_record["total_expenses"] == 425.0
    manual_entry_transactions = asyncio.run(
        db["restaurant_finance_transactions"].find({"source_kind": "manual_entry", "source_id": restaurant_record["manual_entry_id"]}).to_list(length=None)
    )
    assert {item["transaction_type"] for item in manual_entry_transactions} == {"bank_collection", "cash_collection"}
    assert sorted((item["payment_channel"], item["amount"]) for item in manual_entry_transactions) == [
        ("bank_transfer", 100.0),
        ("cash", 200.0),
        ("pos", 800.0),
    ]

    month_data_response = client.get(f"/api/v1/restaurant/daily-data?view=month&reference_date={today_iso}", headers=headers)
    assert month_data_response.status_code == 200
    month_data_payload = month_data_response.json()
    assert month_data_payload["total"] >= 1
    assert month_data_payload["items"][0]["total_expenses"] == 425.0

    analytics_response = client.get("/api/v1/restaurant/analytics/overview?period=weekly", headers=headers)
    assert analytics_response.status_code == 200
    analytics_payload = analytics_response.json()
    assert "estimated_profit" not in analytics_payload
    assert len(analytics_payload["supplier_price_alerts"]) >= 1
    assert "Bakery Goods Co" in analytics_payload["supplier_price_alerts"][0]["title"] or analytics_payload["supplier_price_alerts"][0]["title"]


def test_restaurant_data_migration_unifies_legacy_finance_collections(app):
    db = asyncio.run(app.dependency_overrides[get_database]())
    tenant_id = "tenant-migration"
    now = datetime.now(UTC)
    daily_id = ObjectId()
    weekly_id = ObjectId()
    monthly_id = ObjectId()
    document_id = ObjectId()

    asyncio.run(
        db["restaurant_invoices"].insert_one(
            {
                "_id": document_id,
                "tenant_id": tenant_id,
                "supplier_name": "Legacy Supplier",
                "invoice_number": "INV-001",
                "invoice_date": "2026-04-10",
                "status": "processed",
                "total_amount": 150.0,
                "created_at": now,
                "updated_at": now,
            }
        )
    )
    asyncio.run(
        db["restaurant_daily_records"].insert_one(
            {
                "_id": daily_id,
                "tenant_id": tenant_id,
                "business_date": "2026-04-10",
                "total_revenue": 500.0,
                "total_expenses": 200.0,
                "created_at": now,
                "updated_at": now,
            }
        )
    )
    asyncio.run(
        db["restaurant_weekly_records"].insert_one(
            {
                "_id": weekly_id,
                "tenant_id": tenant_id,
                "week_start_date": "2026-04-06",
                "week_end_date": "2026-04-12",
                "total_revenue": 2500.0,
                "total_expenses": 1200.0,
                "created_at": now,
                "updated_at": now,
            }
        )
    )
    asyncio.run(
        db["restaurant_monthly_records"].insert_one(
            {
                "_id": monthly_id,
                "tenant_id": tenant_id,
                "month_key": "2026-04",
                "month_start_date": "2026-04-01",
                "month_end_date": "2026-04-30",
                "total_revenue": 9000.0,
                "total_expenses": 4200.0,
                "created_at": now,
                "updated_at": now,
            }
        )
    )

    asyncio.run(run_data_migrations(db))
    asyncio.run(run_data_migrations(db))

    migrated_document = asyncio.run(db["restaurant_documents"].find_one({"_id": document_id}))
    assert migrated_document is not None
    assert migrated_document["counterparty_name"] == "Legacy Supplier"
    assert migrated_document["migrated_from_collection"] == "restaurant_invoices"

    daily_snapshot = asyncio.run(
        db["restaurant_finance_snapshots"].find_one({"tenant_id": tenant_id, "period_type": "day", "period_key": "2026-04-10"})
    )
    assert daily_snapshot is not None
    assert daily_snapshot["_id"] == daily_id
    assert daily_snapshot["business_date"] == "2026-04-10"

    weekly_snapshot = asyncio.run(
        db["restaurant_finance_snapshots"].find_one({"tenant_id": tenant_id, "period_type": "week", "period_key": "2026-04-06"})
    )
    assert weekly_snapshot is not None
    assert weekly_snapshot["_id"] == weekly_id
    assert weekly_snapshot["week_end_date"] == "2026-04-12"

    monthly_snapshot = asyncio.run(
        db["restaurant_finance_snapshots"].find_one({"tenant_id": tenant_id, "period_type": "month", "period_key": "2026-04"})
    )
    assert monthly_snapshot is not None
    assert monthly_snapshot["_id"] == monthly_id
    assert monthly_snapshot["month_end_date"] == "2026-04-30"

    migration_record = asyncio.run(db["app_migrations"].find_one({"key": MIGRATION_KEY}))
    assert migration_record is not None
    assert migration_record["summary"]["documents_migrated"] == 1
    assert migration_record["summary"]["daily_snapshots_migrated"] == 1


def test_manual_entry_method_one_creates_finance_transactions(client, app):
    seed_subscription_plan(app)
    headers = register_and_login(
        client,
        {
            "full_name": "Method One Owner",
            "email": "method-one@example.com",
            "password": "MethodOne123",
            "phone": "+1555000199",
        },
    )
    select_subscription_plan(client, headers)

    today_iso = datetime.now(UTC).date().isoformat()
    response = client.post(
        "/api/v1/restaurant/manual-entry",
        headers=headers,
        json={
            "method": "method_1",
            "method_one": {
                "business_date": today_iso,
                "pos_payments": 300,
                "cash_withdrawals": 40,
                "cash_in": 250,
                "cash_out": 20,
                "expenses_in_cash": 35,
                "notes": "Method 1 ledger test",
            },
        },
    )
    assert response.status_code == 201

    db = asyncio.run(app.dependency_overrides[get_database]())
    record_id = response.json()["id"]
    transactions = asyncio.run(
        db["restaurant_finance_transactions"].find({"source_kind": "manual_entry", "source_id": record_id}).sort("transaction_type").to_list(length=None)
    )
    assert len(transactions) == 5
    assert sorted((item["transaction_type"], item["payment_channel"], item["amount"]) for item in transactions) == [
        ("bank_collection", "pos", 300.0),
        ("cash_collection", "cash", 250.0),
        ("expense", "cash", 35.0),
        ("withdrawal", "cash", 20.0),
        ("withdrawal", "cash", 40.0),
    ]


def test_restaurant_document_confirm_save_supports_revenue_classification(client, app):
    seed_subscription_plan(app)
    headers = register_and_login(
        client,
        {
            "full_name": "Revenue Owner",
            "email": "revenue@example.com",
            "password": "RevenuePass123",
            "phone": "+3900000002",
        },
    )
    select_subscription_plan(client, headers)

    business_date = datetime.now(UTC).date().isoformat()
    confirm_response = client.post(
        "/api/v1/restaurant/documents/confirm-save",
        headers=headers,
        json={
            "document_type": "revenue",
            "document_label": "Revenue",
            "counterparty_name": "Dining Room Sales",
            "supplier_name": "Dining Room Sales",
            "invoice_number": "REV-001",
            "invoice_date": business_date,
            "total_amount": 920.0,
            "currency": "EUR",
            "expense_amount": 0.0,
            "cash_amount": 0.0,
            "revenue_amount": 920.0,
            "profit_amount": 0.0,
            "line_items": [],
            "source_file_name": "revenue-summary.pdf",
            "ai_provider": "fallback",
            "ai_summary": "Revenue summary uploaded.",
        },
    )
    assert confirm_response.status_code == 201
    confirm_payload = confirm_response.json()
    assert confirm_payload["document_type"] == "revenue"
    assert confirm_payload["revenue_amount"] == 920.0
    assert confirm_payload["expense_amount"] == 0.0

    date_data_response = client.get(f"/api/v1/restaurant/daily-data?view=date&reference_date={business_date}", headers=headers)
    assert date_data_response.status_code == 200
    date_payload = date_data_response.json()
    assert date_payload["items"][0]["business_date"] == business_date
    assert date_payload["items"][0]["total_revenue"] == 920.0
    assert date_payload["items"][0]["total_expenses"] == 0.0

    db = asyncio.run(app.dependency_overrides[get_database]())
    restaurant_record = asyncio.run(
        db["restaurant_finance_snapshots"].find_one({"period_type": "day", "business_date": business_date})
    )
    assert restaurant_record is not None
    assert restaurant_record["total_revenue"] == 920.0
    assert restaurant_record["total_expenses"] == 0.0
    assert restaurant_record["profit"] == 920.0


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

    today_iso = datetime.now(UTC).date().isoformat()

    expense_response = client.post(
        "/api/v1/restaurant/expenses",
        headers=headers_user_one,
        json={"category": "Staff Costs", "amount": 420.0, "expense_date": today_iso, "section": "bank", "notes": "Payroll"},
    )
    assert expense_response.status_code == 201
    assert expense_response.json()["section"] == "bank"

    bank_account_one_response = client.post(
        "/api/v1/restaurant/cash/bank-accounts",
        headers=headers_user_one,
        json={"bank_account": "Chase Bank - Main"},
    )
    assert bank_account_one_response.status_code == 201
    assert bank_account_one_response.json()["bank_account"] == "Chase Bank - Main"

    bank_account_duplicate_response = client.post(
        "/api/v1/restaurant/cash/bank-accounts",
        headers=headers_user_one,
        json={"bank_account": "  chase bank - main  "},
    )
    assert bank_account_duplicate_response.status_code == 409
    assert bank_account_duplicate_response.json()["error"]["code"] == "conflict"

    bank_account_two_response = client.post(
        "/api/v1/restaurant/cash/bank-accounts",
        headers=headers_user_two,
        json={"bank_account": "City Bank - Payroll"},
    )
    assert bank_account_two_response.status_code == 201

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
    assert set(expenses_user_two.json().keys()) == {"today", "this_week", "this_month"}
    assert expenses_user_two.json()["today"]["total"] == 0
    assert expenses_user_two.json()["this_week"]["items"] == []

    expenses_user_one = client.get("/api/v1/restaurant/expenses", headers=headers_user_one)
    assert expenses_user_one.status_code == 200
    assert expenses_user_one.json()["this_month"]["top_category"] == "Staff Costs"
    assert expenses_user_one.json()["this_month"]["distribution"][0]["label"] == "Staff Costs"

    bank_accounts_user_one = client.get("/api/v1/restaurant/cash/bank-accounts", headers=headers_user_one)
    assert bank_accounts_user_one.status_code == 200
    assert bank_accounts_user_one.json()["total_accounts"] == 1
    assert [item["bank_account"] for item in bank_accounts_user_one.json()["items"]] == ["Chase Bank - Main"]

    bank_accounts_user_two = client.get("/api/v1/restaurant/cash/bank-accounts", headers=headers_user_two)
    assert bank_accounts_user_two.status_code == 200
    assert bank_accounts_user_two.json()["total_accounts"] == 1
    assert [item["bank_account"] for item in bank_accounts_user_two.json()["items"]] == ["City Bank - Payroll"]

    inventory_user_two = client.get("/api/v1/restaurant/inventory", headers=headers_user_two)
    assert inventory_user_two.status_code == 200
    assert inventory_user_two.json()["total"] == 0

    inventory_detail_user_two = client.get(f"/api/v1/restaurant/inventory/{inventory_id}", headers=headers_user_two)
    assert inventory_detail_user_two.status_code == 404

    inventory_detail_user_one = client.get(f"/api/v1/restaurant/inventory/{inventory_id}", headers=headers_user_one)
    assert inventory_detail_user_one.status_code == 200
    inventory_detail_payload = inventory_detail_user_one.json()
    assert inventory_detail_payload["supplier_name"] == "Global Foods Inc."
    assert inventory_detail_payload["current_stock_value"] == 12
    assert "history" in inventory_detail_payload

    inventory_list_user_one = client.get("/api/v1/restaurant/inventory", headers=headers_user_one)
    assert inventory_list_user_one.status_code == 200
    inventory_list_payload = inventory_list_user_one.json()
    assert inventory_list_payload["total_inventory_value"] == 54.0
    assert inventory_list_payload["items"][0]["id"] == inventory_id

    inventory_update_response = client.patch(
        f"/api/v1/restaurant/inventory/{inventory_id}",
        headers=headers_user_one,
        json={"supplier_name": "Updated Supplier", "alert_threshold": 3},
    )
    assert inventory_update_response.status_code == 200
    assert inventory_update_response.json()["supplier_name"] == "Updated Supplier"

    inventory_stock_response = client.post(
        f"/api/v1/restaurant/inventory/{inventory_id}/stock-update",
        headers=headers_user_one,
        json={"add_stock": 5, "remove_stock": 2},
    )
    assert inventory_stock_response.status_code == 200
    assert inventory_stock_response.json()["current_stock_value"] == 15

    inventory_delete_response = client.delete(f"/api/v1/restaurant/inventory/{inventory_id}", headers=headers_user_one)
    assert inventory_delete_response.status_code == 204


def test_restaurant_bank_account_endpoints_create_list_and_scope(client, app):
    seed_subscription_plan(app)
    headers_user_one = register_and_login(
        client,
        {
            "full_name": "Bank Owner One",
            "email": "bank-owner1@example.com",
            "password": "BankOwnerOne123",
            "phone": "+1555000101",
        },
    )
    select_subscription_plan(client, headers_user_one)

    headers_user_two = register_and_login(
        client,
        {
            "full_name": "Bank Owner Two",
            "email": "bank-owner2@example.com",
            "password": "BankOwnerTwo123",
            "phone": "+1555000102",
        },
    )
    select_subscription_plan(client, headers_user_two)

    create_first_response = client.post(
        "/api/v1/restaurant/cash/bank-accounts",
        headers=headers_user_one,
        json={"bank_account": "Chase Bank - Main"},
    )
    assert create_first_response.status_code == 201
    assert create_first_response.json()["bank_account"] == "Chase Bank - Main"

    create_second_response = client.post(
        "/api/v1/restaurant/cash/bank-accounts",
        headers=headers_user_one,
        json={"bank_account": "Citi Bank - Payroll"},
    )
    assert create_second_response.status_code == 201

    duplicate_response = client.post(
        "/api/v1/restaurant/cash/bank-accounts",
        headers=headers_user_one,
        json={"bank_account": "  chase bank - main  "},
    )
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["error"]["code"] == "conflict"

    other_user_response = client.post(
        "/api/v1/restaurant/cash/bank-accounts",
        headers=headers_user_two,
        json={"bank_account": "City Bank - Branch"},
    )
    assert other_user_response.status_code == 201

    user_one_list_response = client.get("/api/v1/restaurant/cash/bank-accounts", headers=headers_user_one)
    assert user_one_list_response.status_code == 200
    user_one_payload = user_one_list_response.json()
    assert user_one_payload["total_accounts"] == 2
    assert [item["bank_account"] for item in user_one_payload["items"]] == ["Chase Bank - Main", "Citi Bank - Payroll"]
    assert [item["deposited_amount"] for item in user_one_payload["items"]] == [0.0, 0.0]

    user_two_list_response = client.get("/api/v1/restaurant/cash/bank-accounts", headers=headers_user_two)
    assert user_two_list_response.status_code == 200
    user_two_payload = user_two_list_response.json()
    assert user_two_payload["total_accounts"] == 1
    assert [item["bank_account"] for item in user_two_payload["items"]] == ["City Bank - Branch"]
    assert [item["deposited_amount"] for item in user_two_payload["items"]] == [0.0]


def test_restaurant_bank_account_update_and_delete_endpoints(client, app):
    seed_subscription_plan(app)
    headers = register_and_login(
        client,
        {
            "full_name": "Bank Account Editor",
            "email": "bankeditor@example.com",
            "password": "BankEditor123",
            "phone": "+15550008888",
        },
    )
    select_subscription_plan(client, headers)

    first_create_response = client.post(
        "/api/v1/restaurant/cash/bank-accounts",
        headers=headers,
        json={"bank_account": "Main Bank"},
    )
    second_create_response = client.post(
        "/api/v1/restaurant/cash/bank-accounts",
        headers=headers,
        json={"bank_account": "Payroll Bank"},
    )
    assert first_create_response.status_code == 201
    assert second_create_response.status_code == 201

    account_id = first_create_response.json()["id"]
    duplicate_update_response = client.patch(
        f"/api/v1/restaurant/cash/bank-accounts/{account_id}",
        headers=headers,
        json={"bank_account": "Payroll Bank"},
    )
    assert duplicate_update_response.status_code == 409

    update_response = client.patch(
        f"/api/v1/restaurant/cash/bank-accounts/{account_id}",
        headers=headers,
        json={"bank_account": "Main Bank Updated"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["bank_account"] == "Main Bank Updated"
    assert update_response.json()["deposited_amount"] == 0.0

    delete_response = client.delete(
        f"/api/v1/restaurant/cash/bank-accounts/{second_create_response.json()['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 204

    list_response = client.get("/api/v1/restaurant/cash/bank-accounts", headers=headers)
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total_accounts"] == 1
    assert [item["bank_account"] for item in payload["items"]] == ["Main Bank Updated"]


def test_restaurant_bank_account_list_includes_deposited_amount_by_bank_name(client, app):
    seed_subscription_plan(app)
    headers = register_and_login(
        client,
        {
            "full_name": "Bank Totals User",
            "email": "banktotals@example.com",
            "password": "BankTotals123",
            "phone": "+15550007777",
        },
    )
    select_subscription_plan(client, headers)

    create_main_response = client.post(
        "/api/v1/restaurant/cash/bank-accounts",
        headers=headers,
        json={"bank_account": "Chase Bank - Main"},
    )
    create_payroll_response = client.post(
        "/api/v1/restaurant/cash/bank-accounts",
        headers=headers,
        json={"bank_account": "Citi Bank - Payroll"},
    )
    assert create_main_response.status_code == 201
    assert create_payroll_response.status_code == 201

    today_iso = datetime.now(UTC).date().isoformat()
    assert client.post(
        "/api/v1/restaurant/cash/deposits",
        headers=headers,
        json={"deposit_date": today_iso, "amount": 125.0, "bank_account": "Chase Bank - Main", "notes": "Main deposit"},
    ).status_code == 201
    assert client.post(
        "/api/v1/restaurant/cash/deposits",
        headers=headers,
        json={"deposit_date": today_iso, "amount": 75.0, "bank_account": "Chase Bank - Main", "notes": "Second deposit"},
    ).status_code == 201
    assert client.post(
        "/api/v1/restaurant/cash/deposits",
        headers=headers,
        json={"deposit_date": today_iso, "amount": 40.0, "bank_account": "Citi Bank - Payroll", "notes": "Payroll deposit"},
    ).status_code == 201

    list_response = client.get("/api/v1/restaurant/cash/bank-accounts", headers=headers)
    assert list_response.status_code == 200
    payload = list_response.json()
    amounts_by_name = {item["bank_account"]: item["deposited_amount"] for item in payload["items"]}
    assert amounts_by_name["Chase Bank - Main"] == 200.0
    assert amounts_by_name["Citi Bank - Payroll"] == 40.0


def test_restaurant_cash_deposit_update_and_delete_endpoints(client, app):
    seed_subscription_plan(app)
    headers = register_and_login(
        client,
        {
            "full_name": "Deposit Editor",
            "email": "depositeditor@example.com",
            "password": "DepositEditor123",
            "phone": "+15550009998",
        },
    )
    select_subscription_plan(client, headers)

    assert client.post(
        "/api/v1/restaurant/cash/bank-accounts",
        headers=headers,
        json={"bank_account": "Main Bank"},
    ).status_code == 201
    assert client.post(
        "/api/v1/restaurant/cash/bank-accounts",
        headers=headers,
        json={"bank_account": "Secondary Bank"},
    ).status_code == 201

    today = datetime.now(UTC).date()
    tomorrow = today + timedelta(days=1)

    create_response = client.post(
        "/api/v1/restaurant/cash/deposits",
        headers=headers,
        json={
            "deposit_date": today.isoformat(),
            "amount": 100.0,
            "type": "bank_deposit",
            "bank_account": "Main Bank",
            "notes": "Initial deposit",
        },
    )
    assert create_response.status_code == 201
    deposit_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/restaurant/cash/deposits/{deposit_id}",
        headers=headers,
        json={
            "deposit_date": tomorrow.isoformat(),
            "amount": 150.0,
            "type": "cash_deposit",
            "bank_account": "Secondary Bank",
            "notes": "Updated deposit",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["amount"] == 150.0
    assert update_response.json()["type"] == "cash_deposit"
    assert update_response.json()["bank_account"] == "Secondary Bank"
    assert update_response.json()["notes"] == "Updated deposit"
    assert update_response.json()["deposit_date"][:10] == tomorrow.isoformat()

    bank_account_list_response = client.get("/api/v1/restaurant/cash/bank-accounts", headers=headers)
    assert bank_account_list_response.status_code == 200
    amounts_by_name = {item["bank_account"]: item["deposited_amount"] for item in bank_account_list_response.json()["items"]}
    assert amounts_by_name["Main Bank"] == 0.0
    assert amounts_by_name["Secondary Bank"] == 150.0

    delete_response = client.delete(f"/api/v1/restaurant/cash/deposits/{deposit_id}", headers=headers)
    assert delete_response.status_code == 204

    bank_account_list_after_delete_response = client.get("/api/v1/restaurant/cash/bank-accounts", headers=headers)
    assert bank_account_list_after_delete_response.status_code == 200
    amounts_after_delete = {item["bank_account"]: item["deposited_amount"] for item in bank_account_list_after_delete_response.json()["items"]}
    assert amounts_after_delete["Main Bank"] == 0.0
    assert amounts_after_delete["Secondary Bank"] == 0.0


def test_cash_management_uses_daily_entries_expenses_invoices_and_deposits(client, app):
    seed_subscription_plan(app)
    headers = register_and_login(
        client,
        {
            "full_name": "Cash Flow Owner",
            "email": "cashflow@example.com",
            "password": "CashFlow123",
            "phone": "+1555000201",
        },
    )
    select_subscription_plan(client, headers)

    today_iso = datetime.now(UTC).date().isoformat()

    confirm_response = client.post(
        "/api/v1/restaurant/documents/confirm-save",
        headers=headers,
        json={
            "supplier_name": "Fresh Foods Ltd",
            "invoice_number": "INV-CASH-001",
            "invoice_date": today_iso,
            "total_amount": 80.0,
            "line_items": [
                {"product_name": "Rice", "quantity": 2, "unit_price": 40.0, "total_price": 80.0}
            ],
            "source_file_name": "invoice-today.png",
            "ai_provider": "fallback",
            "ai_summary": "Imported invoice",
        },
    )
    assert confirm_response.status_code == 201

    daily_response = client.post(
        "/api/v1/restaurant/manual-entry",
        headers=headers,
        json={
            "method": "method_2",
            "method_two": {
                "business_date": today_iso,
                "pos_payments": 700,
                "cash_payments": 300,
                "bank_transfer_payments": 0,
                "lunch_covers": 20,
                "dinner_covers": 30,
                "opening_cash": 100,
                "closing_cash": 400,
            },
        },
    )
    assert daily_response.status_code == 201

    expense_response = client.post(
        "/api/v1/restaurant/expenses",
        headers=headers,
        json={"category": "Cleaning Supplies", "amount": 50.0, "expense_date": today_iso, "section": "cash", "notes": "Paid in cash"},
    )
    assert expense_response.status_code == 201
    assert expense_response.json()["section"] == "cash"

    deposit_response = client.post(
        "/api/v1/restaurant/cash/deposits",
        headers=headers,
        json={"deposit_date": today_iso, "amount": 125.0, "type": "bank_deposit", "bank_account": "Chase Bank - Main", "notes": "Daily bank drop"},
    )
    assert deposit_response.status_code == 201
    assert deposit_response.json()["type"] == "bank_deposit"

    cash_deposit_response = client.post(
        "/api/v1/restaurant/cash/deposits",
        headers=headers,
        json={"deposit_date": today_iso, "amount": 25.0, "type": "cash_deposit", "bank_account": "Chase Bank - Main", "notes": "Daily cash deposit"},
    )
    assert cash_deposit_response.status_code == 201
    assert cash_deposit_response.json()["type"] == "cash_deposit"

    cash_overview_response = client.get("/api/v1/restaurant/cash/overview", headers=headers)
    assert cash_overview_response.status_code == 200
    cash_overview_payload = cash_overview_response.json()
    assert cash_overview_payload["periods"]["today"]["summary"]["total_collected"] == 1000.0
    assert cash_overview_payload["periods"]["today"]["summary"]["bank_deposits"] == 825.0
    assert cash_overview_payload["periods"]["today"]["summary"]["cash_available"] == 200.0
    assert {item["display_title"] for item in cash_overview_payload["periods"]["today"]["recent_deposits"]} >= {"Chase Bank - Main", "POS Settlement"}

    home_response = client.get("/api/v1/restaurant/home?period=weekly", headers=headers)
    assert home_response.status_code == 200
    weekly_cash_cards = {item["label"]: item["amount"] for item in home_response.json()["weekly"]["cash_management"]}
    assert weekly_cash_cards["Total Cash Collected"] == 1000.0
    assert weekly_cash_cards["Cash Deposited"] == 850.0
    assert weekly_cash_cards["Cash Available"] == 200.0

    db = asyncio.run(app.dependency_overrides[get_database]())
    daily_aggregate = asyncio.run(
        db["restaurant_finance_snapshots"].find_one({"period_type": "day", "business_date": today_iso})
    )
    assert daily_aggregate is not None
    assert daily_aggregate["bank_deposits_total"] == 825.0
    assert daily_aggregate["cash_deposits_total"] == 25.0
    assert daily_aggregate["deposits_collection_total"] == 850.0
    assert daily_aggregate["cash_collected_total"] == 1000.0
    assert daily_aggregate["cash_available"] == 200.0

    month_aggregate = asyncio.run(
        db["restaurant_finance_snapshots"].find_one(
            {"period_type": "month", "month_key": datetime.now(UTC).date().strftime("%Y-%m")}
        )
    )
    assert month_aggregate is not None
    assert month_aggregate["bank_deposits_total"] == 825.0
    assert month_aggregate["cash_deposits_total"] == 25.0
    assert month_aggregate["deposits_collection_total"] == 850.0
    assert month_aggregate["cash_available"] == 200.0


def test_restaurant_cash_api_contracts_remain_stable(client, app):
    seed_subscription_plan(app)
    headers = register_and_login(
        client,
        {
            "full_name": "Contract Owner",
            "email": "contract-owner@example.com",
            "password": "ContractOwner123",
            "phone": "+1555000301",
        },
    )
    select_subscription_plan(client, headers)

    today_iso = datetime.now(UTC).date().isoformat()

    expense_response = client.post(
        "/api/v1/restaurant/expenses",
        headers=headers,
        json={
            "category": "Utilities",
            "amount": 40.0,
            "expense_date": today_iso,
            "section": "bank",
            "notes": "Electricity",
        },
    )
    assert expense_response.status_code == 201
    assert set(expense_response.json().keys()) == {"id", "category", "amount", "expense_date", "section", "notes", "created_at"}

    bank_account_response = client.post(
        "/api/v1/restaurant/cash/bank-accounts",
        headers=headers,
        json={"bank_account": "Primary Bank"},
    )
    assert bank_account_response.status_code == 201
    assert set(bank_account_response.json().keys()) == {"id", "bank_account", "deposited_amount", "created_at"}

    deposit_response = client.post(
        "/api/v1/restaurant/cash/deposits",
        headers=headers,
        json={
            "deposit_date": today_iso,
            "amount": 10.0,
            "type": "bank_deposit",
            "bank_account": "Primary Bank",
            "notes": "Drop",
        },
    )
    assert deposit_response.status_code == 201
    assert set(deposit_response.json().keys()) == {
        "id",
        "deposit_date",
        "amount",
        "type",
        "bank_account",
        "notes",
        "created_at",
        "amount_formatted",
        "deposit_date_formatted",
        "display_title",
    }

    bank_account_list_response = client.get("/api/v1/restaurant/cash/bank-accounts", headers=headers)
    assert bank_account_list_response.status_code == 200
    assert set(bank_account_list_response.json().keys()) == {"total_accounts", "items"}
    assert set(bank_account_list_response.json()["items"][0].keys()) == {"id", "bank_account", "deposited_amount", "created_at"}

    cash_overview_response = client.get("/api/v1/restaurant/cash/overview", headers=headers)
    assert cash_overview_response.status_code == 200
    payload = cash_overview_response.json()
    assert set(payload.keys()) == {"active_period", "periods"}
    assert set(payload["periods"].keys()) == {"today", "this_week", "this_month"}
    assert set(payload["periods"]["today"].keys()) == {"summary", "status", "recent_deposits"}
    assert set(payload["periods"]["today"]["summary"].keys()) == {"total_collected", "cash_available", "withdrawals_total", "bank_deposits"}


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

    today = datetime.now(UTC).date()
    previous_day = today - timedelta(days=1)
    previous_day_iso = previous_day.isoformat()
    today_iso = today.isoformat()

    create_daily_response = client.post(
        "/api/v1/restaurant/manual-entry",
        headers=headers,
        json={
            "method": "method_2",
            "method_two": {
                "business_date": previous_day_iso,
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
        json={"category": "Food Supplies", "amount": 250.0, "expense_date": previous_day_iso},
    )

    home_response = client.get("/api/v1/restaurant/home?period=weekly", headers=headers)
    assert home_response.status_code == 200
    home_payload = home_response.json()
    assert home_payload["available_periods"] == ["weekly", "monthly"]
    assert home_payload["weekly"]["metrics"][0]["label"] == "Revenue"
    assert home_payload["monthly"]["metrics"][0]["label"] == "Revenue"
    assert home_payload["weekly"]["revenue"][0]["label"] in ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    assert home_payload["monthly"]["revenue"][0]["label"].startswith("Week ")

    home_monthly_response = client.get("/api/v1/restaurant/home?period=monthly", headers=headers)
    assert home_monthly_response.status_code == 200
    assert "monthly" in home_monthly_response.json()

    home_export_pdf_response = client.get("/api/v1/restaurant/home/export?period=weekly&format=pdf", headers=headers)
    assert home_export_pdf_response.status_code == 200
    assert home_export_pdf_response.headers["content-type"].startswith("application/pdf")

    home_export_excel_response = client.get("/api/v1/restaurant/home/export?period=monthly&format=excel", headers=headers)
    assert home_export_excel_response.status_code == 200
    assert "text/csv" in home_export_excel_response.headers["content-type"]

    home_custom_range_response = client.get(f"/api/v1/restaurant/home?period=weekly&from_date={previous_day_iso}&to_date={today_iso}", headers=headers)
    assert home_custom_range_response.status_code == 200
    assert "weekly" in home_custom_range_response.json()

    home_export_custom_range_response = client.get(f"/api/v1/restaurant/home/export?period=weekly&format=excel&from_date={previous_day_iso}&to_date={today_iso}", headers=headers)
    assert home_export_custom_range_response.status_code == 200
    assert "text/csv" in home_export_custom_range_response.headers["content-type"]

    cash_deposit_response = client.post(
        "/api/v1/restaurant/cash/deposits",
        headers=headers,
        json={
            "deposit_date": previous_day_iso,
            "amount": 450.0,
            "type": "bank_deposit",
            "bank_account": "Chase Bank - Main",
            "notes": "Chase Bank - Main",
        },
    )
    assert cash_deposit_response.status_code == 201
    assert cash_deposit_response.json()["amount_formatted"] == "$450.00"
    assert cash_deposit_response.json()["type"] == "bank_deposit"
    assert cash_deposit_response.json()["deposit_date_formatted"] == previous_day.strftime("%b %d, %Y")
    assert cash_deposit_response.json()["display_title"] == "Chase Bank - Main"

    cash_overview_response = client.get("/api/v1/restaurant/cash/overview", headers=headers)
    assert cash_overview_response.status_code == 200
    cash_overview_payload = cash_overview_response.json()
    assert cash_overview_payload["active_period"] == "today"
    assert set(cash_overview_payload["periods"].keys()) == {"today", "this_week", "this_month"}
    assert cash_overview_payload["periods"]["this_month"]["summary"]["bank_deposits"] >= 450.0
    assert cash_overview_payload["periods"]["today"]["status"]["cash_available"] == "IN_SAFE"
    assert cash_overview_payload["periods"]["this_month"]["recent_deposits"][0]["display_title"] == "Chase Bank - Main"

    insights_response = client.get("/api/v1/restaurant/insights", headers=headers)
    assert insights_response.status_code == 200
    assert insights_response.json()["title"]
    assert len(insights_response.json()["root_causes"]) == 3
    assert len(insights_response.json()["recommended_actions"]) == 3

    second_daily_response = client.post(
        "/api/v1/restaurant/manual-entry",
        headers=headers,
        json={
            "method": "method_2",
            "method_two": {
                "business_date": today_iso,
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

    daily_list_response = client.get(f"/api/v1/restaurant/daily-data?view=date&reference_date={today_iso}", headers=headers)
    assert daily_list_response.status_code == 200
    daily_list_payload = daily_list_response.json()
    assert set(daily_list_payload.keys()) == {"total", "page", "page_size", "pages", "items"}
    assert daily_list_payload["items"][0]["business_date"] == today_iso
    assert set(daily_list_payload["items"][0].keys()) == {"id", "business_date", "total_revenue", "total_expenses", "total_covers", "avg_revenue_per_cover", "created_at"}
    assert daily_list_payload["items"][0]["total_covers"] == 38
    assert daily_list_payload["items"][0]["total_expenses"] == 0.0
    assert daily_list_payload["items"][0]["avg_revenue_per_cover"] == 24.21

    week_list_response = client.get(f"/api/v1/restaurant/daily-data?view=week&reference_date={today_iso}", headers=headers)
    assert week_list_response.status_code == 200
    week_payload = week_list_response.json()
    assert week_payload["total"] == 2
    assert set(week_payload.keys()) == {"total", "page", "page_size", "pages", "items"}

    detail_id = daily_list_payload["items"][0]["id"]
    detail_response = client.get(f"/api/v1/restaurant/daily-data/{detail_id}", headers=headers)
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["business_date"] == today_iso
    assert detail_payload["revenue_breakdown"][0]["label"] == "POS Payments"
    assert detail_payload["covers_summary"]["total"] == 38
    assert detail_payload["register_summary"]["closing_cash"] == 220

    date_detail_response = client.get(f"/api/v1/restaurant/daily-data/by-date?business_date={today_iso}", headers=headers)
    assert date_detail_response.status_code == 200
    date_detail_payload = date_detail_response.json()
    assert date_detail_payload["business_date"] == today_iso
    assert date_detail_payload["total_revenue"] == 920
    assert date_detail_payload["total_covers"] == 38
    assert date_detail_payload["document_count"] == 0

    week_detail_response = client.get(f"/api/v1/restaurant/daily-data/by-week?reference_date={today_iso}", headers=headers)
    assert week_detail_response.status_code == 200
    week_detail_payload = week_detail_response.json()
    assert week_detail_payload["business_date"] == today_iso
    assert week_detail_payload["total_revenue"] == 2220
    assert week_detail_payload["total_covers"] == 143
    assert week_detail_payload["document_count"] == 0

    date_reference_detail_response = client.get(f"/api/v1/restaurant/daily-data/by-date-reference?reference_date={today_iso}", headers=headers)
    assert date_reference_detail_response.status_code == 200
    assert date_reference_detail_response.json()["business_date"] == today_iso

    week_business_date_detail_response = client.get(f"/api/v1/restaurant/daily-data/by-week-business-date?business_date={today_iso}", headers=headers)
    assert week_business_date_detail_response.status_code == 200
    assert week_business_date_detail_response.json()["business_date"] == today_iso

    month_list_response = client.get(f"/api/v1/restaurant/daily-data?view=month&reference_date={today_iso}", headers=headers)
    assert month_list_response.status_code == 200
    month_payload = month_list_response.json()
    assert month_payload["total"] == 2
    assert set(month_payload.keys()) == {"total", "page", "page_size", "pages", "items"}

    month_business_date_detail_response = client.get(f"/api/v1/restaurant/daily-data/by-month-business-date?business_date={today_iso}", headers=headers)
    assert month_business_date_detail_response.status_code == 200
    assert month_business_date_detail_response.json()["business_date"] == today_iso

    all_dates_response = client.get("/api/v1/restaurant/daily-data/by-date", headers=headers)
    assert all_dates_response.status_code == 200
    assert set(all_dates_response.json().keys()) == {"total", "items"}

    all_weeks_response = client.get("/api/v1/restaurant/daily-data/by-week", headers=headers)
    assert all_weeks_response.status_code == 200
    assert set(all_weeks_response.json().keys()) == {"total", "items"}

    all_months_response = client.get("/api/v1/restaurant/daily-data/by-month", headers=headers)
    assert all_months_response.status_code == 200
    assert set(all_months_response.json().keys()) == {"total", "items"}

    delete_response = client.delete(f"/api/v1/restaurant/daily-data/{detail_id}", headers=headers)
    assert delete_response.status_code == 204
    after_delete_response = client.get(f"/api/v1/restaurant/daily-data?view=date&reference_date={today_iso}", headers=headers)
    assert after_delete_response.status_code == 200
    assert after_delete_response.json()["total"] == 1

    business_insight_response = client.get("/api/v1/restaurant/analytics/business-insight", headers=headers)
    assert business_insight_response.status_code == 200
    business_insight_payload = business_insight_response.json()
    assert business_insight_payload["title"]
    assert business_insight_payload["subtitle"]

    analytics_response = client.get("/api/v1/restaurant/analytics/overview", headers=headers)
    assert analytics_response.status_code == 200
    analytics_payload = analytics_response.json()
    assert analytics_payload["revenue_total"] == 1300
    assert analytics_payload["insight_banner"]["title"] == business_insight_payload["title"]
    assert analytics_payload["metric_tiles"][0]["label"] == "Estimated Profit"
    assert analytics_payload["metric_tiles"][1]["label"] == "Peak Hour"
    assert analytics_payload["summary_stats"][0]["label"] == "Revenue"
    assert analytics_payload["summary_stats"][0]["value"] == 1300
    assert analytics_payload["revenue_comparison"][0]["label"] == "This Week Revenue"
    assert analytics_payload["covers_activity"][0]["label"] == "Lunch"
    assert analytics_payload["cost_breakdown"][0]["label"] == "Food Cost"
    assert len(analytics_payload["weekly_revenue"]) == 7
    assert len(analytics_payload["supplier_price_alerts"]) >= 1
    assert analytics_payload["supplier_price_alerts"][0]["title"]
    assert analytics_payload["supplier_price_alerts"][0]["subtitle"]


    analytics_monthly_response = client.get("/api/v1/restaurant/analytics/overview?period=monthly", headers=headers)
    assert analytics_monthly_response.status_code == 200
    analytics_monthly_payload = analytics_monthly_response.json()
    assert analytics_monthly_payload["revenue_comparison"][0]["label"] == "This Month Revenue"

    analytics_export_pdf_response = client.get("/api/v1/restaurant/analytics/export?period=weekly&format=pdf", headers=headers)
    assert analytics_export_pdf_response.status_code == 200
    assert analytics_export_pdf_response.headers["content-type"].startswith("application/pdf")

    analytics_export_excel_response = client.get(f"/api/v1/restaurant/analytics/export?period=monthly&format=excel&from_date={previous_day_iso}&to_date={today_iso}", headers=headers)
    assert analytics_export_excel_response.status_code == 200
    assert "text/csv" in analytics_export_excel_response.headers["content-type"]

    chat_list_response = client.get("/api/v1/restaurant/chat/messages", headers=headers)
    assert chat_list_response.status_code == 200
    chat_list_payload = chat_list_response.json()
    assert set(chat_list_payload.keys()) == {"messages"}
    assert len(chat_list_payload["messages"]) >= 1

    chat_response = client.post("/api/v1/restaurant/chat/messages", headers=headers, json={"message": "How can I improve profit?"})
    assert chat_response.status_code == 201
    chat_payload = chat_response.json()
    assert set(chat_payload.keys()) == {"messages"}
    messages = chat_payload["messages"]
    assert any(message["role"] == "insight" for message in messages)
    assert messages[-1]["role"] == "assistant"
    assert "revenue" in messages[-1]["message"].lower()

    chat_attachment_response = client.post(
        "/api/v1/restaurant/chat/messages/attachments",
        headers=headers,
        data={"message": "Please review this supplier file", "attachment_source": "docs"},
        files={"file": ("suppliers.csv", b"supplier,amount\nBakery Goods Co,425", "text/csv")},
    )
    assert chat_attachment_response.status_code == 201
    chat_attachment_payload = chat_attachment_response.json()
    attachment_messages = [message for message in chat_attachment_payload["messages"] if message.get("attachment_name")]
    assert attachment_messages[-1]["attachment_name"] == "suppliers.csv"
    assert attachment_messages[-1]["attachment_source"] == "docs"
    assert attachment_messages[-1]["role"] == "user"
    assert chat_attachment_payload["messages"][-1]["role"] == "assistant"


    settings_response = client.get("/api/v1/restaurant/settings/profile", headers=headers)
    assert settings_response.status_code == 200
    settings_payload = settings_response.json()
    assert set(settings_payload.keys()) == {
        "full_name",
        "email",
        "phone",
        "restaurant_name",
        "restaurant_type",
        "location",
        "city_location",
        "number_of_seats",
        "preferred_language",
        "profile_image_url",
    }

    settings_update_response = client.put(
        "/api/v1/restaurant/settings/profile",
        headers=headers,
        data={
            "full_name": "Alexander Chen",
            "phone": "+1 (555) 123-4567",
            "restaurant_name": "The Golden Harvest",
            "restaurant_type": "Fine Dining",
            "city_location": "San Francisco",
            "number_of_seats": 120,
        },
        files={"profile_image": ("profile.jpg", b"profile-image-bytes", "image/jpeg")},
    )
    assert settings_update_response.status_code == 200
    updated_settings_payload = settings_update_response.json()
    assert updated_settings_payload["full_name"] == "Alexander Chen"
    assert updated_settings_payload["phone"] == "+1 (555) 123-4567"
    assert updated_settings_payload["restaurant_name"] == "The Golden Harvest"
    assert updated_settings_payload["restaurant_type"] == "Fine Dining"
    assert updated_settings_payload["city_location"] == "San Francisco"
    assert updated_settings_payload["number_of_seats"] == 120
    assert updated_settings_payload["profile_image_url"].startswith("https://")
    assert "/restaurant/profile/" in updated_settings_payload["profile_image_url"]

    db = asyncio.run(app.dependency_overrides[get_database]())
    updated_user = asyncio.run(db["users"].find_one({"email": "alex@example.com"}))
    assert updated_user["profile_image_url"].startswith("https://")
    assert "/restaurant/profile/" in updated_user["profile_image_url"]


