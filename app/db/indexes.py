from __future__ import annotations

from pymongo import ASCENDING, IndexModel

from motor.motor_asyncio import AsyncIOMotorDatabase


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create essential indexes for production query patterns."""
    await db["users"].create_indexes(
        [
            IndexModel([("email", ASCENDING)], unique=True, name="uq_users_email"),
            IndexModel([("restaurant_ids", ASCENDING)], name="idx_users_restaurant_ids"),
            IndexModel([("branch_ids", ASCENDING)], name="idx_users_branch_ids"),
        ],
    )
    await db["restaurants"].create_indexes(
        [
            IndexModel([("owner_id", ASCENDING)], name="idx_restaurants_owner_id"),
            IndexModel([("created_at", ASCENDING)], name="idx_restaurants_created_at"),
        ],
    )
    await db["branches"].create_indexes(
        [
            IndexModel([("restaurant_id", ASCENDING)], name="idx_branches_restaurant_id"),
            IndexModel([("created_at", ASCENDING)], name="idx_branches_created_at"),
        ],
    )
    await db["menu_categories"].create_indexes(
        [
            IndexModel([("restaurant_id", ASCENDING)], name="idx_categories_restaurant_id"),
            IndexModel([("created_at", ASCENDING)], name="idx_categories_created_at"),
        ],
    )
    await db["menu_items"].create_indexes(
        [
            IndexModel([("restaurant_id", ASCENDING)], name="idx_menu_items_restaurant_id"),
            IndexModel([("branch_id", ASCENDING)], name="idx_menu_items_branch_id"),
            IndexModel([("category_id", ASCENDING)], name="idx_menu_items_category_id"),
            IndexModel([("availability", ASCENDING)], name="idx_menu_items_availability"),
            IndexModel([("created_at", ASCENDING)], name="idx_menu_items_created_at"),
        ],
    )
    await db["customers"].create_indexes(
        [
            IndexModel([("restaurant_id", ASCENDING)], name="idx_customers_restaurant_id"),
            IndexModel([("branch_id", ASCENDING)], name="idx_customers_branch_id"),
            IndexModel([("created_at", ASCENDING)], name="idx_customers_created_at"),
        ],
    )
    await db["orders"].create_indexes(
        [
            IndexModel([("restaurant_id", ASCENDING)], name="idx_orders_restaurant_id"),
            IndexModel([("branch_id", ASCENDING)], name="idx_orders_branch_id"),
            IndexModel([("customer_id", ASCENDING)], name="idx_orders_customer_id"),
            IndexModel([("order_status", ASCENDING)], name="idx_orders_order_status"),
            IndexModel([("created_at", ASCENDING)], name="idx_orders_created_at"),
        ],
    )
    await db["analytics_snapshots"].create_indexes(
        [
            IndexModel([("restaurant_id", ASCENDING)], name="idx_analytics_restaurant_id"),
            IndexModel([("generated_at", ASCENDING)], name="idx_analytics_generated_at"),
        ],
    )
    await db["ai_insights"].create_indexes(
        [
            IndexModel([("restaurant_id", ASCENDING)], name="idx_ai_insights_restaurant_id"),
            IndexModel([("insight_type", ASCENDING)], name="idx_ai_insights_type"),
            IndexModel([("generated_at", ASCENDING)], name="idx_ai_insights_generated_at"),
        ],
    )
    await db["notifications"].create_indexes(
        [
            IndexModel([("user_id", ASCENDING)], name="idx_notifications_user_id"),
            IndexModel([("restaurant_id", ASCENDING)], name="idx_notifications_restaurant_id"),
            IndexModel([("created_at", ASCENDING)], name="idx_notifications_created_at"),
        ],
    )
