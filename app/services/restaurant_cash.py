from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

SALE_TRANSACTION_TYPES = {"bank_collection", "cash_collection", "bank_deposit", "cash_deposit"}


@dataclass(frozen=True)
class CashLedgerSummary:
    total_collected: float
    base_cash_available: float
    cash_available: float
    withdrawals_total: float
    direct_bank_collection_total: float
    manual_bank_deposits_total: float
    manual_expenses_total: float
    cash_expenses_total: float
    document_expense_total: float
    document_cash_total: float
    document_revenue_total: float
    document_profit_total: float
    bank_deposits_total: float
    cash_deposits_total: float
    deposits_collection_total: float


def calculate_cash_ledger(
    *,
    daily_records: Iterable[dict[str, Any]],
    finance_transactions: Iterable[dict[str, Any]],
) -> CashLedgerSummary:
    daily_items = list(daily_records)
    transaction_items = list(finance_transactions)

    total_collected = round(
        sum(float(item.get("cash_collected_total", item.get("cash_payments", 0) + item.get("cash_in", 0))) for item in daily_items),
        2,
    )
    base_cash_available = round(
        sum(float(item.get("cash_available", item.get("closing_cash", 0) + item.get("cash_in", 0) - item.get("cash_out", 0))) for item in daily_items),
        2,
    )
    withdrawals_total = round(
        sum(float(item.get("cash_withdrawals", 0) + item.get("cash_out", 0)) for item in daily_items),
        2,
    )
    direct_bank_collection_total = round(
        sum(float(item.get("pos_payments", 0)) + float(item.get("bank_transfer_payments", 0)) for item in daily_items),
        2,
    )
    manual_expenses_total = round(
        sum(
            float(item.get("amount", 0))
            for item in transaction_items
            if str(item.get("transaction_type", "")).lower() == "expense" and str(item.get("source_kind", "")).lower() == "expense"
        ),
        2,
    )
    cash_expenses_total = round(
        sum(
            float(item.get("amount", 0))
            for item in transaction_items
            if str(item.get("transaction_type", "")).lower() == "expense"
            and str(item.get("source_kind", "")).lower() == "expense"
            and str(item.get("payment_channel", "cash")).lower() == "cash"
        ),
        2,
    )
    document_expense_total = round(
        sum(
            float(item.get("amount", 0))
            for item in transaction_items
            if str(item.get("transaction_type", "")).lower() == "expense" and str(item.get("source_kind", "")).lower() == "document"
        ),
        2,
    )
    document_cash_total = round(
        sum(
            float(item.get("amount", 0))
            for item in transaction_items
            if str(item.get("transaction_type", "")).lower() == "cash_collection" and str(item.get("source_kind", "")).lower() == "document"
        ),
        2,
    )
    document_revenue_total = round(
        sum(
            float(item.get("amount", 0))
            for item in transaction_items
            if str(item.get("transaction_type", "")).lower() == "bank_collection" and str(item.get("source_kind", "")).lower() == "document"
        ),
        2,
    )
    document_profit_total = round(
        sum(
            float(item.get("amount", 0))
            for item in transaction_items
            if str(item.get("transaction_type", "")).lower() == "profit_adjustment"
        ),
        2,
    )
    manual_bank_deposits_total = round(
        sum(float(item.get("amount", 0)) for item in transaction_items if str(item.get("transaction_type", "")).lower() == "bank_deposit"),
        2,
    )
    cash_deposits_total = round(
        sum(float(item.get("amount", 0)) for item in transaction_items if str(item.get("transaction_type", "")).lower() == "cash_deposit"),
        2,
    )
    bank_deposits_total = round(manual_bank_deposits_total + direct_bank_collection_total, 2)
    deposits_collection_total = round(bank_deposits_total + cash_deposits_total, 2)
    cash_available = round(
        max(base_cash_available + document_cash_total - cash_expenses_total - document_expense_total - manual_bank_deposits_total - cash_deposits_total, 0.0),
        2,
    )

    return CashLedgerSummary(
        total_collected=round(
            total_collected
            + direct_bank_collection_total
            + document_cash_total
            + manual_bank_deposits_total
            + cash_deposits_total,
            2,
        ),
        base_cash_available=base_cash_available,
        cash_available=cash_available,
        withdrawals_total=withdrawals_total,
        direct_bank_collection_total=direct_bank_collection_total,
        manual_bank_deposits_total=manual_bank_deposits_total,
        manual_expenses_total=manual_expenses_total,
        cash_expenses_total=cash_expenses_total,
        document_expense_total=document_expense_total,
        document_cash_total=document_cash_total,
        document_revenue_total=document_revenue_total,
        document_profit_total=document_profit_total,
        bank_deposits_total=bank_deposits_total,
        cash_deposits_total=cash_deposits_total,
        deposits_collection_total=deposits_collection_total,
    )


def build_aggregate_snapshot(
    *,
    manual_records: Iterable[dict[str, Any]],
    finance_transactions: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    manual_record_items = list(manual_records)
    transaction_items = list(finance_transactions)

    cash = calculate_cash_ledger(
        daily_records=manual_record_items,
        finance_transactions=transaction_items,
    )
    manual_sales_total = round(sum(float(item.get("total_revenue", 0)) for item in manual_record_items), 2)
    deposit_sales_total = round(
        sum(
            float(item.get("amount", 0))
            for item in transaction_items
            if str(item.get("source_kind", "")).lower() == "deposit"
            and str(item.get("transaction_type", "")).lower() in SALE_TRANSACTION_TYPES
        ),
        2,
    )
    document_sales_total = round(
        sum(
            float(item.get("amount", 0))
            for item in transaction_items
            if str(item.get("source_kind", "")).lower() == "document"
            and str(item.get("transaction_type", "")).lower() in SALE_TRANSACTION_TYPES
        ),
        2,
    )
    other_sales_total = round(
        sum(
            float(item.get("amount", 0))
            for item in transaction_items
            if str(item.get("source_kind", "")).lower() not in {"manual_entry", "document", "deposit"}
            and str(item.get("transaction_type", "")).lower() in SALE_TRANSACTION_TYPES
        ),
        2,
    )

    total_revenue = round(manual_sales_total + deposit_sales_total + other_sales_total, 2)
    manual_entry_expenses = round(sum(float(item.get("total_expenses", 0)) for item in manual_record_items), 2)
    lunch_covers = int(sum(int(item.get("lunch_covers", 0)) for item in manual_record_items))
    dinner_covers = int(sum(int(item.get("dinner_covers", 0)) for item in manual_record_items))
    total_covers = lunch_covers + dinner_covers
    total_expenses = round(manual_entry_expenses + cash.manual_expenses_total + cash.document_expense_total, 2)
    net_revenue_total = round(total_revenue - total_expenses, 2)
    calculated_profit = net_revenue_total

    snapshot = {
        "total_revenue": total_revenue,
        "manual_entry_expenses": manual_entry_expenses,
        "manual_expense_total": cash.manual_expenses_total,
        "manual_expense_cash_total": cash.cash_expenses_total,
        "uploaded_document_total": cash.document_expense_total,
        "direct_bank_collection_total": cash.direct_bank_collection_total,
        "manual_bank_deposits_total": cash.manual_bank_deposits_total,
        "document_expense_total": cash.document_expense_total,
        "document_cash_total": cash.document_cash_total,
        "document_revenue_total": cash.document_revenue_total,
        "document_profit_total": cash.document_profit_total,
        "bank_deposits_total": cash.bank_deposits_total,
        "cash_deposits_total": cash.cash_deposits_total,
        "deposits_collection_total": cash.deposits_collection_total,
        "cash_collected_total": cash.total_collected,
        "base_cash_available": cash.base_cash_available,
        "cash_available": cash.cash_available,
        "withdrawals_total": cash.withdrawals_total,
        "total_expenses": total_expenses,
        "profit": calculated_profit,
        "lunch_covers": lunch_covers,
        "dinner_covers": dinner_covers,
        "total_covers": total_covers,
        "avg_revenue_per_cover": round(total_revenue / max(total_covers, 1), 2) if total_revenue else 0.0,
        "revenue_summary": {
            "sales_total": total_revenue,
            "manual_entry_sales_total": manual_sales_total,
            "deposit_sales_total": deposit_sales_total,
            "document_sales_total": document_sales_total,
            "other_sales_total": other_sales_total,
            "recognized_revenue_total": total_revenue,
            "net_revenue_total": net_revenue_total,
            "document_revenue_total": cash.document_revenue_total,
            "document_profit_adjustment_total": cash.document_profit_total,
        },
        "expense_summary": {
            "total_expenses": total_expenses,
            "manual_entry_expenses": manual_entry_expenses,
            "manual_expense_total": cash.manual_expenses_total,
            "manual_cash_expense_total": cash.cash_expenses_total,
            "document_expense_total": cash.document_expense_total,
        },
        "deposit_summary": {
            "direct_bank_collection_total": cash.direct_bank_collection_total,
            "manual_bank_deposits_total": cash.manual_bank_deposits_total,
            "cash_deposits_total": cash.cash_deposits_total,
            "bank_deposits_total": cash.bank_deposits_total,
            "deposits_collection_total": cash.deposits_collection_total,
        },
        "cash_summary": {
            "cash_collected_total": cash.total_collected,
            "base_cash_available": cash.base_cash_available,
            "cash_available": cash.cash_available,
            "withdrawals_total": cash.withdrawals_total,
            "document_cash_total": cash.document_cash_total,
        },
        "operations_summary": {
            "profit": calculated_profit,
            "lunch_covers": lunch_covers,
            "dinner_covers": dinner_covers,
            "total_covers": total_covers,
            "avg_revenue_per_cover": round(total_revenue / max(total_covers, 1), 2) if total_revenue else 0.0,
        },
    }
    snapshot.update({f"cash_{key}": value for key, value in asdict(cash).items() if key not in {"cash_available"}})
    return snapshot
