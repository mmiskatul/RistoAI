from __future__ import annotations

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import OperationFailure

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase

from app.db.collections import CoreCollections, RestaurantCollections


async def _create_indexes_safely(collection: AsyncIOMotorCollection, indexes: list[IndexModel]) -> None:
    try:
        await collection.create_indexes(indexes)
        return
    except OperationFailure as exc:
        if exc.code != 86:
            raise

    existing_indexes = {index["name"]: index for index in await collection.list_indexes().to_list(length=None)}
    dropped_any = False
    for index in indexes:
        index_name = index.document["name"]
        existing = existing_indexes.get(index_name)
        if existing is None:
            continue
        existing_key = list(existing.get("key", {}).items())
        requested_key = list(index.document.get("key", {}).items())
        existing_unique = bool(existing.get("unique", False))
        requested_unique = bool(index.document.get("unique", False))
        existing_ttl = existing.get("expireAfterSeconds")
        requested_ttl = index.document.get("expireAfterSeconds")
        if existing_key != requested_key or existing_unique != requested_unique or existing_ttl != requested_ttl:
            await collection.drop_index(index_name)
            dropped_any = True

    if dropped_any:
        await collection.create_indexes(indexes)
        return

    raise


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create indexes for core auth/support data and restaurant operational data."""
    await _create_indexes_safely(
        db[CoreCollections.USERS],
        [
            IndexModel([("email", ASCENDING)], unique=True, name="uq_users_email"),
            IndexModel([("role", ASCENDING), ("created_at", DESCENDING)], name="idx_users_role_created"),
        ],
    )
    await _create_indexes_safely(
        db[CoreCollections.AUTH_CODES],
        [
            IndexModel(
                [("email", ASCENDING), ("purpose", ASCENDING), ("created_at", ASCENDING)],
                name="idx_auth_codes_email_purpose_created",
            ),
            IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl_auth_codes_expires_at"),
        ],
    )
    await _create_indexes_safely(
        db[CoreCollections.ONBOARDING_PROFILES],
        [
            IndexModel([("user_id", ASCENDING)], unique=True, name="uq_onboarding_profiles_user_id"),
            IndexModel([("restaurant_type", ASCENDING)], name="idx_onboarding_profiles_restaurant_type"),
        ],
    )
    await _create_indexes_safely(
        db[CoreCollections.SUBSCRIPTION_PLANS],
        [
            IndexModel([("singleton_key", ASCENDING)], unique=True, name="uq_subscription_plan_singleton_key"),
            IndexModel([("is_active", ASCENDING), ("is_visible", ASCENDING)], name="idx_subscription_plan_active_visible"),
        ],
    )
    await _create_indexes_safely(
        db[CoreCollections.USER_SUBSCRIPTIONS],
        [
            IndexModel([("user_id", ASCENDING), ("created_at", ASCENDING)], name="idx_user_subscriptions_user_created"),
            IndexModel([("user_id", ASCENDING), ("is_current", ASCENDING)], name="idx_user_subscriptions_user_current"),
            IndexModel([("subscription_plan_id", ASCENDING)], name="idx_user_subscriptions_plan_id"),
            IndexModel([("status", ASCENDING)], name="idx_user_subscriptions_status"),
        ],
    )
    await _create_indexes_safely(
        db[CoreCollections.SUPPORT_TICKETS],
        [
            IndexModel([("ticket_number", ASCENDING)], unique=True, name="uq_support_tickets_number"),
            IndexModel([("user_id", ASCENDING), ("created_at", ASCENDING)], name="idx_support_tickets_user_created"),
            IndexModel([("status", ASCENDING)], name="idx_support_tickets_status"),
        ],
    )
    await _create_indexes_safely(
        db[CoreCollections.COUPONS],
        [
            IndexModel([("code", ASCENDING)], unique=True, name="uq_coupons_code"),
            IndexModel([("status", ASCENDING), ("expires_at", ASCENDING)], name="idx_coupons_status_expires"),
        ],
    )
    await _create_indexes_safely(
        db[RestaurantCollections.INVOICES],
        [
            IndexModel([("tenant_id", ASCENDING), ("invoice_date", DESCENDING)], name="idx_restaurant_invoices_tenant_invoice_date"),
            IndexModel([("tenant_id", ASCENDING), ("created_at", DESCENDING)], name="idx_restaurant_invoices_tenant_created"),
            IndexModel([("tenant_id", ASCENDING), ("status", ASCENDING)], name="idx_restaurant_invoices_tenant_status"),
            IndexModel([("tenant_id", ASCENDING), ("supplier_name", ASCENDING)], name="idx_restaurant_invoices_tenant_supplier"),
            IndexModel([("tenant_id", ASCENDING), ("invoice_number", ASCENDING)], name="idx_restaurant_invoices_tenant_number"),
        ],
    )
    await _create_indexes_safely(
        db[RestaurantCollections.EXPENSES],
        [
            IndexModel([("tenant_id", ASCENDING), ("expense_date", DESCENDING)], name="idx_restaurant_expenses_tenant_date"),
            IndexModel([("tenant_id", ASCENDING), ("category", ASCENDING)], name="idx_restaurant_expenses_tenant_category"),
        ],
    )
    await _create_indexes_safely(
        db[RestaurantCollections.CASH_DEPOSITS],
        [
            IndexModel([("tenant_id", ASCENDING), ("deposit_date", DESCENDING)], name="idx_restaurant_cash_tenant_date"),
        ],
    )
    await _create_indexes_safely(
        db[RestaurantCollections.BANK_ACCOUNTS],
        [
            IndexModel([("tenant_id", ASCENDING), ("normalized_name", ASCENDING)], unique=True, name="uq_restaurant_bank_accounts_tenant_name"),
            IndexModel([("tenant_id", ASCENDING), ("bank_account", ASCENDING)], name="idx_restaurant_bank_accounts_tenant_account"),
        ],
    )
    await _create_indexes_safely(
        db[RestaurantCollections.MANUAL_ENTRIES],
        [
            IndexModel([("tenant_id", ASCENDING), ("business_date", ASCENDING)], unique=True, name="uq_restaurant_manual_entries_tenant_date"),
            IndexModel([("tenant_id", ASCENDING), ("updated_at", DESCENDING)], name="idx_restaurant_manual_entries_tenant_updated"),
        ],
    )
    await _create_indexes_safely(
        db[RestaurantCollections.DAILY_RECORDS],
        [
            IndexModel([("tenant_id", ASCENDING), ("business_date", ASCENDING)], unique=True, name="uq_restaurant_daily_records_tenant_date"),
            IndexModel([("tenant_id", ASCENDING), ("updated_at", DESCENDING)], name="idx_restaurant_daily_records_tenant_updated"),
        ],
    )
    await _create_indexes_safely(
        db[RestaurantCollections.WEEKLY_RECORDS],
        [
            IndexModel([("tenant_id", ASCENDING), ("week_start_date", ASCENDING)], unique=True, name="uq_restaurant_weekly_records_tenant_week"),
            IndexModel([("tenant_id", ASCENDING), ("updated_at", DESCENDING)], name="idx_restaurant_weekly_records_tenant_updated"),
        ],
    )
    await _create_indexes_safely(
        db[RestaurantCollections.MONTHLY_RECORDS],
        [
            IndexModel([("tenant_id", ASCENDING), ("month_key", ASCENDING)], unique=True, name="uq_restaurant_monthly_records_tenant_month"),
            IndexModel([("tenant_id", ASCENDING), ("updated_at", DESCENDING)], name="idx_restaurant_monthly_records_tenant_updated"),
        ],
    )
    await _create_indexes_safely(
        db[RestaurantCollections.INVENTORY_ITEMS],
        [
            IndexModel([("tenant_id", ASCENDING), ("product_name", ASCENDING)], name="idx_restaurant_inventory_tenant_name"),
            IndexModel([("tenant_id", ASCENDING), ("stock_status", ASCENDING)], name="idx_restaurant_inventory_tenant_status"),
            IndexModel([("tenant_id", ASCENDING), ("category", ASCENDING)], name="idx_restaurant_inventory_tenant_category"),
        ],
    )
    await _create_indexes_safely(
        db[RestaurantCollections.CHAT_MESSAGES],
        [
            IndexModel([("tenant_id", ASCENDING), ("created_at", ASCENDING)], name="idx_restaurant_chat_tenant_created"),
        ],
    )
    await _create_indexes_safely(
        db[RestaurantCollections.AI_INSIGHTS],
        [
            IndexModel([("tenant_id", ASCENDING), ("created_at", DESCENDING)], name="idx_restaurant_insights_tenant_created"),
        ],
    )
