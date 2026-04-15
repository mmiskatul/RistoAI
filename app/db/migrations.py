from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.collections import CoreCollections, RestaurantCollections

logger = logging.getLogger(__name__)

MIGRATION_KEY = "2026_04_restaurant_finance_snapshot_unification"
LEGACY_DOCUMENTS_COLLECTION = "restaurant_invoices"
LEGACY_DAILY_SNAPSHOTS_COLLECTION = "restaurant_daily_records"
LEGACY_WEEKLY_SNAPSHOTS_COLLECTION = "restaurant_weekly_records"
LEGACY_MONTHLY_SNAPSHOTS_COLLECTION = "restaurant_monthly_records"


async def run_data_migrations(db: AsyncIOMotorDatabase) -> None:
    migration_collection = db[CoreCollections.MIGRATIONS]
    existing = await migration_collection.find_one({"key": MIGRATION_KEY})
    if existing:
        return

    summary = {
        "documents_migrated": await _migrate_documents(db),
        "daily_snapshots_migrated": await _migrate_daily_snapshots(db),
        "weekly_snapshots_migrated": await _migrate_weekly_snapshots(db),
        "monthly_snapshots_migrated": await _migrate_monthly_snapshots(db),
    }

    await migration_collection.update_one(
        {"key": MIGRATION_KEY},
        {
            "$set": {
                "key": MIGRATION_KEY,
                "summary": summary,
                "completed_at": datetime.now(UTC),
            }
        },
        upsert=True,
    )
    logger.info("Restaurant data migration completed", extra={"migration_key": MIGRATION_KEY, "summary": summary})


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
