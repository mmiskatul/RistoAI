from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.collections import CoreCollections, RestaurantCollections
from app.services.restaurant_cash import build_aggregate_snapshot

logger = logging.getLogger(__name__)

SNAPSHOT_UNIFICATION_MIGRATION_KEY = "2026_04_restaurant_finance_snapshot_unification"
MANUAL_ENTRY_NORMALIZATION_MIGRATION_KEY = "2026_06_restaurant_manual_entry_normalization"
LEGACY_DOCUMENTS_COLLECTION = "restaurant_invoices"
LEGACY_DAILY_SNAPSHOTS_COLLECTION = "restaurant_daily_records"
LEGACY_WEEKLY_SNAPSHOTS_COLLECTION = "restaurant_weekly_records"
LEGACY_MONTHLY_SNAPSHOTS_COLLECTION = "restaurant_monthly_records"


async def run_data_migrations(db: AsyncIOMotorDatabase) -> None:
    await _run_migration_once(
        db,
        key=SNAPSHOT_UNIFICATION_MIGRATION_KEY,
        execute=_run_snapshot_unification_migration,
    )
    await _run_migration_once(
        db,
        key=MANUAL_ENTRY_NORMALIZATION_MIGRATION_KEY,
        execute=_run_manual_entry_normalization_migration,
    )


async def _run_migration_once(
    db: AsyncIOMotorDatabase,
    *,
    key: str,
    execute: Any,
) -> None:
    migration_collection = db[CoreCollections.MIGRATIONS]
    existing = await migration_collection.find_one({"key": key})
    if existing:
        return

    summary = await execute(db)
    await migration_collection.update_one(
        {"key": key},
        {
            "$set": {
                "key": key,
                "summary": summary,
                "completed_at": datetime.now(UTC),
            }
        },
        upsert=True,
    )
    logger.info("Restaurant data migration completed", extra={"migration_key": key, "summary": summary})


async def _run_snapshot_unification_migration(db: AsyncIOMotorDatabase) -> dict[str, int]:
    return {
        "documents_migrated": await _migrate_documents(db),
        "daily_snapshots_migrated": await _migrate_daily_snapshots(db),
        "weekly_snapshots_migrated": await _migrate_weekly_snapshots(db),
        "monthly_snapshots_migrated": await _migrate_monthly_snapshots(db),
    }


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _parse_business_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _resolve_method_1_cash_bounds(document: dict[str, Any]) -> tuple[float, float]:
    opening_cash = _safe_float(document.get("opening_cash"))
    closing_cash = _safe_float(document.get("closing_cash"))
    legacy_initial_cash = _safe_float(document.get("cash_in"))
    legacy_final_cash = _safe_float(document.get("cash_out"))
    if opening_cash == 0 and closing_cash == 0 and (legacy_initial_cash or legacy_final_cash):
        return legacy_initial_cash, legacy_final_cash
    return opening_cash, closing_cash


def _normalize_manual_entry_document(document: dict[str, Any], *, normalized_at: datetime) -> dict[str, Any]:
    payload = dict(document)
    method = str(payload.get("method") or "")
    pos_payments = _safe_float(payload.get("pos_payments"))
    expenses_in_cash = round(_safe_float(payload.get("expenses_in_cash")), 2)

    if method == "method_1":
        opening_cash, closing_cash = _resolve_method_1_cash_bounds(payload)
        cash_withdrawals = round(_safe_float(payload.get("cash_withdrawals")), 2)
        total_revenue = round(
            pos_payments + cash_withdrawals + expenses_in_cash + closing_cash - opening_cash,
            2,
        )
        payload.update(
            {
                "opening_cash": round(opening_cash, 2),
                "closing_cash": round(closing_cash, 2),
                "cash_withdrawals": cash_withdrawals,
                "cash_in": round(opening_cash, 2),
                "cash_out": round(closing_cash, 2),
                "cash_collected_total": total_revenue,
                "cash_available": round(max(closing_cash, 0.0), 2),
                "total_revenue": total_revenue,
                "total_expenses": expenses_in_cash,
                "profit": round(total_revenue - expenses_in_cash, 2),
                "lunch_covers": 0,
                "dinner_covers": 0,
                "avg_revenue_per_cover": round(total_revenue / 1, 2),
            }
        )
    elif method == "method_2":
        opening_cash = round(_safe_float(payload.get("opening_cash")), 2)
        closing_cash = round(_safe_float(payload.get("closing_cash")), 2)
        cash_payments = round(_safe_float(payload.get("cash_payments")), 2)
        bank_transfer_payments = round(_safe_float(payload.get("bank_transfer_payments")), 2)
        expected_closing_cash = round(opening_cash + cash_payments - expenses_in_cash, 2)
        cash_difference = round(closing_cash - expected_closing_cash, 2)
        register_cash_out = round(max(expected_closing_cash - closing_cash, 0.0), 2)
        total_revenue = round(pos_payments + cash_payments + bank_transfer_payments, 2)
        payload.update(
            {
                "opening_cash": opening_cash,
                "closing_cash": closing_cash,
                "cash_payments": cash_payments,
                "bank_transfer_payments": bank_transfer_payments,
                "cash_withdrawals": 0.0,
                "cash_in": cash_payments,
                "cash_out": register_cash_out,
                "cash_difference": cash_difference,
                "cash_collected_total": round(cash_payments + pos_payments, 2),
                "cash_available": round(max(cash_payments - register_cash_out - expenses_in_cash, 0.0), 2),
                "total_revenue": total_revenue,
                "total_expenses": expenses_in_cash,
                "profit": round(total_revenue - expenses_in_cash, 2),
                "lunch_covers": 0,
                "dinner_covers": 0,
                "avg_revenue_per_cover": round(total_revenue / 1, 2),
            }
        )

    payload["schema_version"] = 2
    payload["normalized_at"] = normalized_at
    return payload


def _build_manual_entry_finance_transactions(record: dict[str, Any], *, created_at: datetime) -> list[dict[str, Any]]:
    business_date = str(record.get("business_date") or "")
    if not business_date:
        return []

    transactions: list[dict[str, Any]] = []

    def add_transaction(*, transaction_type: str, amount: float, payment_channel: str, reference_label: str) -> None:
        resolved_amount = round(max(float(amount or 0), 0.0), 2)
        if resolved_amount <= 0:
            return
        ledger_group = {
            "bank_collection": "sale",
            "cash_collection": "sale",
            "withdrawal": "cash_movement",
            "expense": "expense",
        }.get(transaction_type, "other")
        transactions.append(
            {
                "business_date": business_date,
                "transaction_type": transaction_type,
                "payment_channel": payment_channel,
                "amount": resolved_amount,
                "currency": "EUR",
                "reference_label": reference_label,
                "created_at": created_at,
                "updated_at": created_at,
                "metadata": {
                    "method": record.get("method"),
                    "manual_entry_id": str(record.get("_id")),
                    "ledger_group": ledger_group,
                    "affects_revenue": transaction_type in {"bank_collection", "cash_collection"},
                    "affects_cash": transaction_type in {"cash_collection", "withdrawal", "expense"},
                    "affects_profit": transaction_type == "expense",
                },
            }
        )

    if str(record.get("method") or "") == "method_1":
        add_transaction(transaction_type="bank_collection", amount=_safe_float(record.get("pos_payments")), payment_channel="pos", reference_label="POS Payments")
        add_transaction(transaction_type="withdrawal", amount=_safe_float(record.get("cash_withdrawals")), payment_channel="cash", reference_label="Cash Withdrawals")
        add_transaction(transaction_type="expense", amount=_safe_float(record.get("expenses_in_cash")), payment_channel="cash", reference_label="Expenses in Cash")
        return transactions

    add_transaction(transaction_type="bank_collection", amount=_safe_float(record.get("pos_payments")), payment_channel="pos", reference_label="POS Payments")
    add_transaction(transaction_type="cash_collection", amount=_safe_float(record.get("cash_payments")), payment_channel="cash", reference_label="Cash Payments")
    add_transaction(transaction_type="bank_collection", amount=_safe_float(record.get("bank_transfer_payments")), payment_channel="bank_transfer", reference_label="Bank Transfer Payments")
    return transactions


def _build_manual_entry_cash_deposits(record: dict[str, Any], *, created_at: datetime) -> list[dict[str, Any]]:
    tenant_id = record.get("tenant_id")
    source_id = str(record.get("_id"))
    business_date = _parse_business_date(record.get("business_date"))
    if not tenant_id or not source_id or business_date is None:
        return []

    deposit_rows: list[dict[str, Any]] = []

    def add_deposit(*, source_subtype: str, amount: float, deposit_type: str, bank_account: str, notes: str | None) -> None:
        resolved_amount = round(max(float(amount or 0), 0.0), 2)
        if resolved_amount <= 0:
            return
        deposit_rows.append(
            {
                "tenant_id": tenant_id,
                "deposit_date": datetime.combine(business_date, datetime.min.time(), tzinfo=UTC),
                "amount": resolved_amount,
                "type": deposit_type,
                "bank_account": bank_account,
                "notes": notes,
                "source_kind": "manual_entry",
                "source_id": source_id,
                "source_subtype": source_subtype,
                "created_by_user_id": str(record.get("created_by_user_id") or ""),
                "created_at": created_at,
                "updated_at": created_at,
            }
        )

    notes = str(record.get("notes") or "Entered from daily data")
    add_deposit(source_subtype="pos_payments", amount=_safe_float(record.get("pos_payments")), deposit_type="pos_payment", bank_account="POS Settlement", notes="Entered from daily data")

    if str(record.get("method") or "") == "method_2":
        add_deposit(source_subtype="cash_payments", amount=_safe_float(record.get("cash_payments")), deposit_type="cash_in", bank_account="Cash Payments", notes="Entered from daily data")
        add_deposit(source_subtype="bank_transfer_payments", amount=_safe_float(record.get("bank_transfer_payments")), deposit_type="bank_transfer_payment", bank_account="Bank Transfer Collection", notes="Entered from daily data")
        add_deposit(source_subtype="cash_out", amount=_safe_float(record.get("cash_out")), deposit_type="cash_out", bank_account="Register Cash Out", notes="Entered from daily data")
        add_deposit(source_subtype="expenses_in_cash", amount=_safe_float(record.get("expenses_in_cash")), deposit_type="cash_expense", bank_account="Expenses in Cash", notes="Entered from daily data")
        return deposit_rows

    add_deposit(source_subtype="cash_withdrawals", amount=_safe_float(record.get("cash_withdrawals")), deposit_type="cash_withdrawal", bank_account="Cash Withdrawals", notes=notes)
    add_deposit(source_subtype="expenses_in_cash", amount=_safe_float(record.get("expenses_in_cash")), deposit_type="cash_expense", bank_account="Expenses in Cash", notes=notes)
    return deposit_rows


def _summarize_daily_bucket_document(document: dict[str, Any]) -> dict[str, float]:
    document_type = str(document.get("document_type") or "").lower()
    expense_amount = _safe_float(document.get("expense_amount"))
    if expense_amount <= 0 and document_type == "expense":
        expense_amount = _safe_float(document.get("total_amount"))
    return {
        "revenue": round(_safe_float(document.get("cash_amount")) + _safe_float(document.get("revenue_amount")), 2),
        "invoice_total": round(expense_amount if document_type == "expense" else 0.0, 2),
    }


def _merge_inventory_usage_entries(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for record in records:
        for usage in record.get("inventory_usage") or []:
            item_id = str(usage.get("inventory_item_id") or "")
            if not item_id:
                continue
            current = merged.setdefault(
                item_id,
                {
                    "inventory_item_id": item_id,
                    "product_name": str(usage.get("product_name") or ""),
                    "quantity_used": 0.0,
                    "unit_type": str(usage.get("unit_type") or ""),
                    "unit_cost": _safe_float(usage.get("unit_cost")),
                    "total_cost": 0.0,
                },
            )
            current["quantity_used"] = round(current["quantity_used"] + _safe_float(usage.get("quantity_used")), 2)
            current["total_cost"] = round(current["total_cost"] + _safe_float(usage.get("total_cost")), 2)
            if not current.get("product_name"):
                current["product_name"] = str(usage.get("product_name") or "")
            if not current.get("unit_type"):
                current["unit_type"] = str(usage.get("unit_type") or "")
    return list(merged.values())


async def _refresh_daily_snapshot(
    db: AsyncIOMotorDatabase,
    *,
    tenant_id: str,
    business_date: str,
    refreshed_at: datetime,
) -> None:
    finance_snapshots = db[RestaurantCollections.FINANCE_SNAPSHOTS]
    manual_entries = await db[RestaurantCollections.MANUAL_ENTRIES].find(
        {"tenant_id": tenant_id, "business_date": business_date}
    ).to_list(length=None)

    day_start = datetime.combine(date.fromisoformat(business_date), datetime.min.time(), tzinfo=UTC)
    day_end = day_start + timedelta(days=1)

    expenses = await db[RestaurantCollections.EXPENSES].find(
        {
            "tenant_id": tenant_id,
            "expense_date": {"$gte": day_start, "$lt": day_end},
        }
    ).to_list(length=None)
    documents = await db[RestaurantCollections.DOCUMENTS].find(
        {
            "tenant_id": tenant_id,
            "status": "processed",
            "invoice_date": business_date,
        }
    ).to_list(length=None)
    deposits = await db[RestaurantCollections.CASH_DEPOSITS].find(
        {
            "tenant_id": tenant_id,
            "deposit_date": {"$gte": day_start, "$lt": day_end},
        }
    ).to_list(length=None)
    finance_transactions = await db[RestaurantCollections.FINANCE_TRANSACTIONS].find(
        {
            "tenant_id": tenant_id,
            "business_date": business_date,
        }
    ).to_list(length=None)

    snapshot = build_aggregate_snapshot(
        manual_records=manual_entries,
        finance_transactions=finance_transactions,
    )
    uploaded_document_total = round(
        sum(_summarize_daily_bucket_document(item)["invoice_total"] for item in documents),
        2,
    )
    manual_expenses = [
        item
        for item in expenses
        if str(item.get("source_kind") or "").lower() not in {"manual_entry", "document"}
    ]
    primary_manual_record = manual_entries[0] if manual_entries else None

    await finance_snapshots.update_one(
        {
            "tenant_id": tenant_id,
            "period_type": "day",
            "period_key": business_date,
        },
        {
            "$set": {
                "period_type": "day",
                "period_key": business_date,
                "period_start_date": business_date,
                "period_end_date": business_date,
                "manual_entry_id": str(primary_manual_record.get("_id")) if primary_manual_record else None,
                "manual_entry_ids": [str(item.get("_id")) for item in manual_entries],
                "manual_entry_count": len(manual_entries),
                "manual_method": primary_manual_record.get("method") if primary_manual_record else None,
                "manual_revenue": snapshot["revenue_summary"]["manual_entry_sales_total"],
                "manual_entry_expenses": snapshot["manual_entry_expenses"],
                "uploaded_document_total": uploaded_document_total,
                "uploaded_document_count": len(documents),
                "uploaded_document_ids": [str(item.get("_id")) for item in documents],
                "manual_expense_total": snapshot["manual_expense_total"],
                "manual_expense_cash_total": snapshot["manual_expense_cash_total"],
                "manual_expense_count": len(manual_expenses),
                "manual_expense_ids": [str(item.get("_id")) for item in manual_expenses],
                "bank_deposits_total": snapshot["bank_deposits_total"],
                "cash_deposits_total": snapshot["cash_deposits_total"],
                "deposits_collection_total": snapshot["deposits_collection_total"],
                "bank_deposit_count": len(deposits),
                "bank_deposit_ids": [str(item.get("_id")) for item in deposits],
                "cash_collected_total": snapshot["cash_collected_total"],
                "pos_payments_total": snapshot["pos_payments_total"],
                "base_cash_available": snapshot["base_cash_available"],
                "cash_available": snapshot["cash_available"],
                "withdrawals_total": snapshot["withdrawals_total"],
                "total_revenue": snapshot["total_revenue"],
                "total_expenses": snapshot["total_expenses"],
                "profit": snapshot["profit"],
                "lunch_covers": snapshot["lunch_covers"],
                "dinner_covers": snapshot["dinner_covers"],
                "total_covers": snapshot["total_covers"],
                "avg_revenue_per_cover": snapshot["avg_revenue_per_cover"],
                "revenue_summary": snapshot["revenue_summary"],
                "expense_summary": snapshot["expense_summary"],
                "deposit_summary": snapshot["deposit_summary"],
                "cash_summary": snapshot["cash_summary"],
                "operations_summary": snapshot["operations_summary"],
                "inventory_usage": _merge_inventory_usage_entries(manual_entries),
                "source_breakdown": {
                    "manual_entry": bool(manual_entries),
                    "manual_entry_count": len(manual_entries),
                    "uploaded_document_count": len(documents),
                    "manual_expense_count": len(manual_expenses),
                    "bank_deposit_count": len(deposits),
                },
                "last_synced_by_user_id": "migration:2026_06_restaurant_manual_entry_normalization",
                "last_synced_at": refreshed_at,
                "updated_at": refreshed_at,
            },
            "$setOnInsert": {
                "tenant_id": tenant_id,
                "created_at": refreshed_at,
            },
        },
        upsert=True,
    )


async def _run_manual_entry_normalization_migration(db: AsyncIOMotorDatabase) -> dict[str, int]:
    manual_entries = db[RestaurantCollections.MANUAL_ENTRIES]
    finance_transactions = db[RestaurantCollections.FINANCE_TRANSACTIONS]
    cash_deposits = db[RestaurantCollections.CASH_DEPOSITS]
    normalized_at = datetime.now(UTC)

    scanned = 0
    updated = 0
    transactions_replaced = 0
    deposits_replaced = 0
    affected_snapshot_keys: set[tuple[str, str]] = set()

    async for document in manual_entries.find({}):
        scanned += 1
        normalized = _normalize_manual_entry_document(document, normalized_at=normalized_at)
        document_id = normalized.pop("_id")
        await manual_entries.update_one({"_id": document_id}, {"$set": normalized})
        updated += 1

        persisted = {**normalized, "_id": document_id}
        tenant_id = str(persisted.get("tenant_id") or "")
        business_date = str(persisted.get("business_date") or "")
        if tenant_id and business_date:
            affected_snapshot_keys.add((tenant_id, business_date))
        source_scope = {
            "tenant_id": persisted.get("tenant_id"),
            "source_kind": "manual_entry",
            "source_id": str(document_id),
        }
        await finance_transactions.delete_many(source_scope)
        normalized_transactions = _build_manual_entry_finance_transactions(persisted, created_at=normalized_at)
        if normalized_transactions:
            await finance_transactions.insert_many(
                [
                    {
                        "tenant_id": persisted.get("tenant_id"),
                        "source_kind": "manual_entry",
                        "source_id": str(document_id),
                        **item,
                    }
                    for item in normalized_transactions
                ]
            )
            transactions_replaced += len(normalized_transactions)

        await cash_deposits.delete_many(source_scope)
        normalized_deposits = _build_manual_entry_cash_deposits(persisted, created_at=normalized_at)
        if normalized_deposits:
            await cash_deposits.insert_many(normalized_deposits)
            deposits_replaced += len(normalized_deposits)

    refreshed_daily_snapshots = 0
    for tenant_id, business_date in sorted(affected_snapshot_keys):
        await _refresh_daily_snapshot(
            db,
            tenant_id=tenant_id,
            business_date=business_date,
            refreshed_at=normalized_at,
        )
        refreshed_daily_snapshots += 1

    return {
        "manual_entries_scanned": scanned,
        "manual_entries_updated": updated,
        "manual_entry_transactions_replaced": transactions_replaced,
        "manual_entry_cash_deposits_replaced": deposits_replaced,
        "daily_snapshots_refreshed": refreshed_daily_snapshots,
    }


async def _migrate_documents(db: AsyncIOMotorDatabase) -> int:
    target_collection_name = RestaurantCollections.DOCUMENTS
    if LEGACY_DOCUMENTS_COLLECTION == target_collection_name:
        return 0

    migrated = 0
    async for document in db[LEGACY_DOCUMENTS_COLLECTION].find({}):
        payload = dict(document)
        payload.setdefault("counterparty_name", payload.get("supplier_name"))
        payload.setdefault("migrated_from_collection", LEGACY_DOCUMENTS_COLLECTION)
        await db[target_collection_name].replace_one({"_id": payload["_id"]}, payload, upsert=True)
        migrated += 1
    return migrated


async def _migrate_daily_snapshots(db: AsyncIOMotorDatabase) -> int:
    migrated = 0
    async for snapshot in db[LEGACY_DAILY_SNAPSHOTS_COLLECTION].find({}):
        business_date = snapshot.get("business_date")
        if not business_date:
            continue
        await _upsert_finance_snapshot(
            db,
            source_snapshot=snapshot,
            period_type="day",
            period_key=str(business_date),
            period_start_date=str(business_date),
            period_end_date=str(business_date),
            legacy_collection=LEGACY_DAILY_SNAPSHOTS_COLLECTION,
        )
        migrated += 1
    return migrated


async def _migrate_weekly_snapshots(db: AsyncIOMotorDatabase) -> int:
    migrated = 0
    async for snapshot in db[LEGACY_WEEKLY_SNAPSHOTS_COLLECTION].find({}):
        week_start_date = snapshot.get("week_start_date")
        if not week_start_date:
            continue
        await _upsert_finance_snapshot(
            db,
            source_snapshot=snapshot,
            period_type="week",
            period_key=str(week_start_date),
            period_start_date=str(week_start_date),
            period_end_date=str(snapshot.get("week_end_date") or week_start_date),
            legacy_collection=LEGACY_WEEKLY_SNAPSHOTS_COLLECTION,
        )
        migrated += 1
    return migrated


async def _migrate_monthly_snapshots(db: AsyncIOMotorDatabase) -> int:
    migrated = 0
    async for snapshot in db[LEGACY_MONTHLY_SNAPSHOTS_COLLECTION].find({}):
        month_key = snapshot.get("month_key")
        if not month_key:
            continue
        await _upsert_finance_snapshot(
            db,
            source_snapshot=snapshot,
            period_type="month",
            period_key=str(month_key),
            period_start_date=str(snapshot.get("month_start_date") or month_key),
            period_end_date=str(snapshot.get("month_end_date") or month_key),
            legacy_collection=LEGACY_MONTHLY_SNAPSHOTS_COLLECTION,
        )
        migrated += 1
    return migrated


async def _upsert_finance_snapshot(
    db: AsyncIOMotorDatabase,
    *,
    source_snapshot: dict[str, Any],
    period_type: str,
    period_key: str,
    period_start_date: str,
    period_end_date: str,
    legacy_collection: str,
) -> None:
    target_collection = db[RestaurantCollections.FINANCE_SNAPSHOTS]
    payload = dict(source_snapshot)
    payload["period_type"] = period_type
    payload["period_key"] = period_key
    payload["period_start_date"] = period_start_date
    payload["period_end_date"] = period_end_date
    payload.setdefault("migrated_from_collection", legacy_collection)
    payload.setdefault("migrated_at", datetime.now(UTC))
    if period_type != "day":
        payload.pop("business_date", None)

    source_id = payload.pop("_id", None)
    update_doc = {
        "$set": payload,
    }
    if isinstance(source_id, ObjectId):
        update_doc["$setOnInsert"] = {"_id": source_id}

    await target_collection.update_one(
        {
            "tenant_id": payload.get("tenant_id"),
            "period_type": period_type,
            "period_key": period_key,
        },
        update_doc,
        upsert=True,
    )
