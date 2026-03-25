from __future__ import annotations

from pymongo import ASCENDING, DESCENDING, IndexModel

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.collections import CoreCollections, RestaurantCollections


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create indexes for core auth/support data and restaurant operational data."""
    await db[CoreCollections.USERS].create_indexes(
        [
            IndexModel([("email", ASCENDING)], unique=True, name="uq_users_email"),
            IndexModel([("role", ASCENDING), ("created_at", DESCENDING)], name="idx_users_role_created"),
        ],
    )
    await db[CoreCollections.AUTH_CODES].create_indexes(
        [
            IndexModel(
                [("email", ASCENDING), ("purpose", ASCENDING), ("created_at", ASCENDING)],
                name="idx_auth_codes_email_purpose_created",
            ),
            IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl_auth_codes_expires_at"),
        ],
    )
    await db[CoreCollections.ONBOARDING_PROFILES].create_indexes(
        [
            IndexModel([("user_id", ASCENDING)], unique=True, name="uq_onboarding_profiles_user_id"),
            IndexModel([("restaurant_type", ASCENDING)], name="idx_onboarding_profiles_restaurant_type"),
        ],
    )
    await db[CoreCollections.SUBSCRIPTION_PLANS].create_indexes(
        [
            IndexModel([("singleton_key", ASCENDING)], unique=True, name="uq_subscription_plan_singleton_key"),
            IndexModel([("is_active", ASCENDING), ("is_visible", ASCENDING)], name="idx_subscription_plan_active_visible"),
        ],
    )
    await db[CoreCollections.USER_SUBSCRIPTIONS].create_indexes(
        [
            IndexModel([("user_id", ASCENDING), ("created_at", ASCENDING)], name="idx_user_subscriptions_user_created"),
            IndexModel([("user_id", ASCENDING), ("is_current", ASCENDING)], name="idx_user_subscriptions_user_current"),
            IndexModel([("subscription_plan_id", ASCENDING)], name="idx_user_subscriptions_plan_id"),
            IndexModel([("status", ASCENDING)], name="idx_user_subscriptions_status"),
        ],
    )
    await db[CoreCollections.SUPPORT_TICKETS].create_indexes(
        [
            IndexModel([("ticket_number", ASCENDING)], unique=True, name="uq_support_tickets_number"),
            IndexModel([("user_id", ASCENDING), ("created_at", ASCENDING)], name="idx_support_tickets_user_created"),
            IndexModel([("status", ASCENDING)], name="idx_support_tickets_status"),
        ],
    )
    await db[CoreCollections.COUPONS].create_indexes(
        [
            IndexModel([("code", ASCENDING)], unique=True, name="uq_coupons_code"),
            IndexModel([("status", ASCENDING), ("expires_at", ASCENDING)], name="idx_coupons_status_expires"),
        ],
    )

    await db[RestaurantCollections.INVOICES].create_indexes(
        [
            IndexModel([("tenant_id", ASCENDING), ("invoice_date", DESCENDING)], name="idx_restaurant_invoices_tenant_invoice_date"),
            IndexModel([("tenant_id", ASCENDING), ("created_at", DESCENDING)], name="idx_restaurant_invoices_tenant_created"),
            IndexModel([("tenant_id", ASCENDING), ("status", ASCENDING)], name="idx_restaurant_invoices_tenant_status"),
            IndexModel([("tenant_id", ASCENDING), ("supplier_name", ASCENDING)], name="idx_restaurant_invoices_tenant_supplier"),
            IndexModel([("tenant_id", ASCENDING), ("invoice_number", ASCENDING)], name="idx_restaurant_invoices_tenant_number"),
        ],
    )
    await db[RestaurantCollections.EXPENSES].create_indexes(
        [
            IndexModel([("tenant_id", ASCENDING), ("expense_date", DESCENDING)], name="idx_restaurant_expenses_tenant_date"),
            IndexModel([("tenant_id", ASCENDING), ("category", ASCENDING)], name="idx_restaurant_expenses_tenant_category"),
        ],
    )
    await db[RestaurantCollections.CASH_DEPOSITS].create_indexes(
        [
            IndexModel([("tenant_id", ASCENDING), ("deposit_date", DESCENDING)], name="idx_restaurant_cash_tenant_date"),
        ],
    )
    await db[RestaurantCollections.MANUAL_ENTRIES].create_indexes(
        [
            IndexModel([("tenant_id", ASCENDING), ("business_date", ASCENDING)], unique=True, name="uq_restaurant_manual_entries_tenant_date"),
            IndexModel([("tenant_id", ASCENDING), ("updated_at", DESCENDING)], name="idx_restaurant_manual_entries_tenant_updated"),
        ],
    )
    await db[RestaurantCollections.DAILY_RECORDS].create_indexes(
        [
            IndexModel([("tenant_id", ASCENDING), ("business_date", ASCENDING)], unique=True, name="uq_restaurant_daily_records_tenant_date"),
            IndexModel([("tenant_id", ASCENDING), ("updated_at", DESCENDING)], name="idx_restaurant_daily_records_tenant_updated"),
        ],
    )
    await db[RestaurantCollections.WEEKLY_RECORDS].create_indexes(
        [
            IndexModel([("tenant_id", ASCENDING), ("week_start_date", ASCENDING)], unique=True, name="uq_restaurant_weekly_records_tenant_week"),
            IndexModel([("tenant_id", ASCENDING), ("updated_at", DESCENDING)], name="idx_restaurant_weekly_records_tenant_updated"),
        ],
    )
    await db[RestaurantCollections.MONTHLY_RECORDS].create_indexes(
        [
            IndexModel([("tenant_id", ASCENDING), ("month_key", ASCENDING)], unique=True, name="uq_restaurant_monthly_records_tenant_month"),
            IndexModel([("tenant_id", ASCENDING), ("updated_at", DESCENDING)], name="idx_restaurant_monthly_records_tenant_updated"),
        ],
    )
    await db[RestaurantCollections.INVENTORY_ITEMS].create_indexes(
        [
            IndexModel([("tenant_id", ASCENDING), ("product_name", ASCENDING)], name="idx_restaurant_inventory_tenant_name"),
            IndexModel([("tenant_id", ASCENDING), ("stock_status", ASCENDING)], name="idx_restaurant_inventory_tenant_status"),
            IndexModel([("tenant_id", ASCENDING), ("category", ASCENDING)], name="idx_restaurant_inventory_tenant_category"),
        ],
    )
    await db[RestaurantCollections.CHAT_MESSAGES].create_indexes(
        [
            IndexModel([("tenant_id", ASCENDING), ("created_at", ASCENDING)], name="idx_restaurant_chat_tenant_created"),
        ],
    )
    await db[RestaurantCollections.AI_INSIGHTS].create_indexes(
        [
            IndexModel([("tenant_id", ASCENDING), ("created_at", DESCENDING)], name="idx_restaurant_insights_tenant_created"),
        ],
    )
