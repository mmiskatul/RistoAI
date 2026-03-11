from __future__ import annotations

from pymongo import ASCENDING, IndexModel

from motor.motor_asyncio import AsyncIOMotorDatabase


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create essential indexes for remaining collections."""
    await db["users"].create_indexes(
        [
            IndexModel([("email", ASCENDING)], unique=True, name="uq_users_email"),
            IndexModel([("restaurant_ids", ASCENDING)], name="idx_users_restaurant_ids"),
            IndexModel([("branch_ids", ASCENDING)], name="idx_users_branch_ids"),
        ],
    )
    await db["auth_codes"].create_indexes(
        [
            IndexModel([("email", ASCENDING), ("purpose", ASCENDING), ("created_at", ASCENDING)], name="idx_auth_codes_email_purpose_created"),
            IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl_auth_codes_expires_at"),
        ],
    )
    await db["ai_insights"].create_indexes(
        [
            IndexModel([("restaurant_id", ASCENDING)], name="idx_ai_insights_restaurant_id"),
            IndexModel([("insight_type", ASCENDING)], name="idx_ai_insights_type"),
            IndexModel([("generated_at", ASCENDING)], name="idx_ai_insights_generated_at"),
        ],
    )
    await db["analytics_snapshots"].create_indexes(
        [
            IndexModel([("restaurant_id", ASCENDING)], name="idx_analytics_restaurant_id"),
            IndexModel([("generated_at", ASCENDING)], name="idx_analytics_generated_at"),
        ],
    )
    await db["notifications"].create_indexes(
        [
            IndexModel([("user_id", ASCENDING)], name="idx_notifications_user_id"),
            IndexModel([("restaurant_id", ASCENDING)], name="idx_notifications_restaurant_id"),
            IndexModel([("created_at", ASCENDING)], name="idx_notifications_created_at"),
        ],
    )
