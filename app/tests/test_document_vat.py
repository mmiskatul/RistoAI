from __future__ import annotations

from app.services.restaurant import RestaurantOperationsService


def _service() -> RestaurantOperationsService:
    return RestaurantOperationsService(
        user_repository=None,
        document_repository=None,
        expense_repository=None,
        food_cost_repository=None,
        cash_repository=None,
        bank_account_repository=None,
        daily_record_repository=None,
        record_repository=None,
        weekly_record_repository=None,
        monthly_record_repository=None,
        finance_transaction_repository=None,
        inventory_repository=None,
        inventory_category_repository=None,
        inventory_supplier_repository=None,
        chat_repository=None,
        insight_repository=None,
        notification_repository=None,
        openai_service=None,
    )


def test_document_line_items_keep_individual_vat_rates() -> None:
    service = _service()

    normalized = service._normalize_document_line_items(
        [
            {"product_name": "Bread", "quantity": 10, "unit_price": 2, "total_price": 20, "vat_rate": 4},
            {"product_name": "Wine", "quantity": 2, "unit_price": 15, "total_price": 30, "vat_rate": 22},
            {"product_name": "Custom item", "quantity": 1, "unit_price": 100, "total_price": 100, "vat_rate": 12.5},
            {"product_name": "Prepared food", "quantity": 1, "unit_price": 50, "total_price": 50},
        ]
    )

    assert normalized[0]["vat_rate"] == 4
    assert normalized[0]["vat_amount"] == 0.8
    assert normalized[1]["vat_rate"] == 22
    assert normalized[1]["vat_amount"] == 6.6
    assert normalized[2]["vat_rate"] == 12.5
    assert normalized[2]["vat_amount"] == 12.5
    assert normalized[3]["vat_rate"] == 10
    assert normalized[3]["vat_amount"] == 5


def test_vat_overview_uses_document_line_vat_totals() -> None:
    service = _service()

    totals = service._calculate_document_vat_totals(
        [
            {
                "status": "processed",
                "document_type": "expense",
                "line_items": [
                    {"product_name": "Bread", "total_price": 20, "vat_rate": 4, "vat_amount": 0.8},
                    {"product_name": "Wine", "total_price": 30, "vat_rate": 22, "vat_amount": 6.6},
                ],
            },
            {
                "status": "processed",
                "document_type": "revenue",
                "line_items": [
                    {"product_name": "Dinner", "total_price": 100, "vat_rate": 10, "vat_amount": 10},
                ],
            },
        ]
    )

    assert totals["receivable"] == 7.4
    assert totals["payable"] == 10
    assert totals["has_receivable"] is True
    assert totals["has_payable"] is True
