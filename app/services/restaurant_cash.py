from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class CashLedgerSummary:
    total_collected: float
    base_cash_available: float
    cash_available: float
    withdrawals_total: float
    manual_expenses_total: float
    cash_expenses_total: float
    uploaded_invoice_total: float
    bank_deposits_total: float


def calculate_cash_ledger(
    *,
    daily_records: Iterable[dict[str, Any]],
    expenses: Iterable[dict[str, Any]],
    documents: Iterable[dict[str, Any]],
    deposits: Iterable[dict[str, Any]],
) -> CashLedgerSummary:
    daily_items = list(daily_records)
    expense_items = list(expenses)
    document_items = list(documents)
    deposit_items = list(deposits)

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
    manual_expenses_total = round(sum(float(item.get("amount", 0)) for item in expense_items), 2)
    cash_expenses_total = round(
        sum(float(item.get("amount", 0)) for item in expense_items if str(item.get("section", "cash")).lower() == "cash"),
        2,
    )
    uploaded_invoice_total = round(
        sum(float(item.get("total_amount", 0)) for item in document_items if item.get("status") == "processed" and item.get("invoice_date")),
        2,
    )
    bank_deposits_total = round(sum(float(item.get("amount", 0)) for item in deposit_items), 2)
    cash_available = round(max(base_cash_available - cash_expenses_total - uploaded_invoice_total - bank_deposits_total, 0.0), 2)

    return CashLedgerSummary(
        total_collected=total_collected,
        base_cash_available=base_cash_available,
        cash_available=cash_available,
        withdrawals_total=withdrawals_total,
        manual_expenses_total=manual_expenses_total,
        cash_expenses_total=cash_expenses_total,
        uploaded_invoice_total=uploaded_invoice_total,
        bank_deposits_total=bank_deposits_total,
    )


def build_aggregate_snapshot(
    *,
    manual_records: Iterable[dict[str, Any]],
    manual_expenses: Iterable[dict[str, Any]],
    uploaded_invoices: Iterable[dict[str, Any]],
    deposits: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    manual_record_items = list(manual_records)
    manual_expense_items = list(manual_expenses)
    uploaded_invoice_items = list(uploaded_invoices)
    deposit_items = list(deposits)

    cash = calculate_cash_ledger(
        daily_records=manual_record_items,
        expenses=manual_expense_items,
        documents=uploaded_invoice_items,
        deposits=deposit_items,
    )
    total_revenue = round(sum(float(item.get("total_revenue", 0)) for item in manual_record_items), 2)
    manual_entry_expenses = round(sum(float(item.get("total_expenses", 0)) for item in manual_record_items), 2)
    lunch_covers = int(sum(int(item.get("lunch_covers", 0)) for item in manual_record_items))
    dinner_covers = int(sum(int(item.get("dinner_covers", 0)) for item in manual_record_items))
    total_covers = lunch_covers + dinner_covers
    total_expenses = round(manual_entry_expenses + cash.manual_expenses_total + cash.uploaded_invoice_total, 2)

    snapshot = {
        "total_revenue": total_revenue,
        "manual_entry_expenses": manual_entry_expenses,
        "manual_expense_total": cash.manual_expenses_total,
        "manual_expense_cash_total": cash.cash_expenses_total,
        "uploaded_invoice_total": cash.uploaded_invoice_total,
        "bank_deposits_total": cash.bank_deposits_total,
        "cash_collected_total": cash.total_collected,
        "base_cash_available": cash.base_cash_available,
        "cash_available": cash.cash_available,
        "withdrawals_total": cash.withdrawals_total,
        "total_expenses": total_expenses,
        "profit": round(total_revenue - total_expenses, 2),
        "lunch_covers": lunch_covers,
        "dinner_covers": dinner_covers,
        "total_covers": total_covers,
        "avg_revenue_per_cover": round(total_revenue / max(total_covers, 1), 2) if total_revenue else 0.0,
    }
    snapshot.update({f"cash_{key}": value for key, value in asdict(cash).items() if key not in {"cash_available"}})
    return snapshot
