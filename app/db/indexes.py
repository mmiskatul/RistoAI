from __future__ import annotations

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import OperationFailure

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase

from app.db.collections import CoreCollections, RestaurantCollections


_INDEX_OPTION_KEYS = (
    "unique",
    "expireAfterSeconds",
    "sparse",
    "partialFilterExpression",
    "collation",
)


def _index_specs_match(existing: dict, requested: dict) -> bool:
    if list(existing.get("key", {}).items()) != list(requested.get("key", {}).items()):
        return False
    return all(existing.get(option_key) == requested.get(option_key) for option_key in _INDEX_OPTION_KEYS)


async def _create_indexes_safely(collection: AsyncIOMotorCollection, indexes: list[IndexModel]) -> None:
    try:
        await collection.create_indexes(indexes)
        return
    except OperationFailure as exc:
        if exc.code not in {85, 86}:
            raise

    existing_indexes = {index["name"]: index for index in await collection.list_indexes().to_list(length=None)}
    indexes_to_create: list[IndexModel] = []
    for index in indexes:
        requested_index = index.document
        index_name = requested_index["name"]
        existing = existing_indexes.get(index_name)

        if existing is not None:
            if _index_specs_match(existing, requested_index):
                continue
            await collection.drop_index(index_name)
            existing_indexes.pop(index_name, None)

        if any(_index_specs_match(existing_index, requested_index) for existing_index in existing_indexes.values()):
            continue

        indexes_to_create.append(index)

    if indexes_to_create:
        await collection.create_indexes(indexes_to_create)
        return

    return


async def _drop_indexes_by_name(collection: AsyncIOMotorCollection, index_names: list[str]) -> None:
    existing_indexes = {index["name"] for index in await collection.list_indexes().to_list(length=None)}
    for index_name in index_names:
        if index_name in existing_indexes:
            await collection.drop_index(index_name)


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
        db[CoreCollections.MIGRATIONS],
        [
            IndexModel([("key", ASCENDING)], unique=True, name="uq_app_migrations_key"),
            IndexModel([("completed_at", DESCENDING)], name="idx_app_migrations_completed"),
        ],
    )
    await _create_indexes_safely(
        db[RestaurantCollections.DOCUMENTS],
        [
            IndexModel([("tenant_id", ASCENDING), ("invoice_date", DESCENDING)], name="idx_restaurant_documents_tenant_invoice_date"),
            IndexModel([("tenant_id", ASCENDING), ("created_at", DESCENDING)], name="idx_restaurant_documents_tenant_created"),
            IndexModel([("tenant_id", ASCENDING), ("status", ASCENDING)], name="idx_restaurant_documents_tenant_status"),
            IndexModel([("tenant_id", ASCENDING), ("supplier_name", ASCENDING)], name="idx_restaurant_documents_tenant_supplier"),
            IndexModel([("tenant_id", ASCENDING), ("invoice_number", ASCENDING)], name="idx_restaurant_documents_tenant_number"),
        ],
    )
    await _create_indexes_safely(
        db[RestaurantCollections.EXPENSES],
        [
            IndexModel([("tenant_id", ASCENDING), ("expense_date", DESCENDING)], name="idx_restaurant_expenses_tenant_date"),
            IndexModel([("tenant_id", ASCENDING), ("category", ASCENDING)], name="idx_restaurant_expenses_tenant_category"),
            IndexModel([("tenant_id", ASCENDING), ("source_kind", ASCENDING), ("source_id", ASCENDING)], name="idx_restaurant_expenses_tenant_source"),
        ],
    )
    await _create_indexes_safely(
        db[RestaurantCollections.CASH_DEPOSITS],
        [
            IndexModel([("tenant_id", ASCENDING), ("deposit_date", DESCENDING)], name="idx_restaurant_cash_tenant_date"),
            IndexModel(
                [("tenant_id", ASCENDING), ("source_kind", ASCENDING), ("source_id", ASCENDING), ("source_subtype", ASCENDING)],
                name="idx_restaurant_cash_tenant_source",
            ),
        ],
    )
    await _create_indexes_safely(
        db[RestaurantCollections.BANK_ACCOUNTS],
        [
            IndexModel([("tenant_id", ASCENDING), ("normalized_name", ASCENDING)], unique=True, name="uq_restaurant_bank_accounts_tenant_name"),
            IndexModel([("tenant_id", ASCENDING), ("bank_account", ASCENDING)], name="idx_restaurant_bank_accounts_tenant_account"),
        ],
    )
    await _drop_indexes_by_name(
        db[RestaurantCollections.MANUAL_ENTRIES],
        [
            "uq_restaurant_manual_entries_tenant_date",
        ],
    )
    await _create_indexes_safely(
        db[RestaurantCollections.MANUAL_ENTRIES],
        [
            IndexModel([("tenant_id", ASCENDING), ("business_date", DESCENDING)], name="idx_restaurant_manual_entries_tenant_business_date"),
            IndexModel([("tenant_id", ASCENDING), ("updated_at", DESCENDING)], name="idx_restaurant_manual_entries_tenant_updated"),
        ],
    )
    await _drop_indexes_by_name(
        db[RestaurantCollections.FINANCE_SNAPSHOTS],
        [
            "uq_restaurant_daily_records_tenant_date",
            "idx_restaurant_daily_records_tenant_business_date",
        ],
    )
    await _create_indexes_safely(
        db[RestaurantCollections.FINANCE_SNAPSHOTS],
        [
            IndexModel([("tenant_id", ASCENDING), ("period_type", ASCENDING), ("period_key", ASCENDING)], unique=True, name="uq_restaurant_finance_snapshots_tenant_period"),
            IndexModel([("tenant_id", ASCENDING), ("period_type", ASCENDING), ("period_start_date", DESCENDING)], name="idx_restaurant_finance_snapshots_tenant_period_start"),
            IndexModel([("tenant_id", ASCENDING), ("period_type", ASCENDING), ("updated_at", DESCENDING)], name="idx_restaurant_finance_snapshots_tenant_period_updated"),
        ],
    )
    await _create_indexes_safely(
        db[RestaurantCollections.FINANCE_TRANSACTIONS],
        [
            IndexModel([("tenant_id", ASCENDING), ("business_date", DESCENDING)], name="idx_restaurant_finance_transactions_tenant_date"),
            IndexModel([("tenant_id", ASCENDING), ("transaction_type", ASCENDING), ("business_date", DESCENDING)], name="idx_restaurant_finance_transactions_tenant_type_date"),
            IndexModel([("tenant_id", ASCENDING), ("source_kind", ASCENDING), ("source_id", ASCENDING)], name="idx_restaurant_finance_transactions_tenant_source"),
            IndexModel([("tenant_id", ASCENDING), ("payment_channel", ASCENDING), ("business_date", DESCENDING)], name="idx_restaurant_finance_transactions_tenant_channel_date"),
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
        db[RestaurantCollections.INVENTORY_CATEGORIES],
        [
            IndexModel([("tenant_id", ASCENDING), ("normalized_name", ASCENDING)], unique=True, name="uq_restaurant_inventory_categories_tenant_name"),
            IndexModel([("tenant_id", ASCENDING), ("name", ASCENDING)], name="idx_restaurant_inventory_categories_tenant_label"),
        ],
    )
    await _create_indexes_safely(
        db[RestaurantCollections.INVENTORY_SUPPLIERS],
        [
            IndexModel([("tenant_id", ASCENDING), ("normalized_name", ASCENDING)], unique=True, name="uq_restaurant_inventory_suppliers_tenant_name"),
            IndexModel([("tenant_id", ASCENDING), ("name", ASCENDING)], name="idx_restaurant_inventory_suppliers_tenant_label"),
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
