from __future__ import annotations

from pymongo import ASCENDING, IndexModel

from motor.motor_asyncio import AsyncIOMotorDatabase


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create essential indexes for auth and onboarding collections."""
    await db["users"].create_indexes(
        [
            IndexModel([("email", ASCENDING)], unique=True, name="uq_users_email"),
        ],
    )
    await db["auth_codes"].create_indexes(
        [
            IndexModel(
                [("email", ASCENDING), ("purpose", ASCENDING), ("created_at", ASCENDING)],
                name="idx_auth_codes_email_purpose_created",
            ),
            IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl_auth_codes_expires_at"),
        ],
    )
    await db["onboarding_profiles"].create_indexes(
        [
            IndexModel([("user_id", ASCENDING)], unique=True, name="uq_onboarding_profiles_user_id"),
            IndexModel([("restaurant_type", ASCENDING)], name="idx_onboarding_profiles_restaurant_type"),
        ],
    )
    await db["subscription_plan"].create_indexes(
        [
            IndexModel([("singleton_key", ASCENDING)], unique=True, name="uq_subscription_plan_singleton_key"),
        ],
    )
    await db["user_subscriptions"].create_indexes(
        [
            IndexModel([("user_id", ASCENDING), ("created_at", ASCENDING)], name="idx_user_subscriptions_user_created"),
            IndexModel([("user_id", ASCENDING), ("is_current", ASCENDING)], name="idx_user_subscriptions_user_current"),
            IndexModel([("subscription_plan_id", ASCENDING)], name="idx_user_subscriptions_plan_id"),
            IndexModel([("status", ASCENDING)], name="idx_user_subscriptions_status"),
        ],
    )

    await db["support_tickets"].create_indexes(
        [
            IndexModel([("ticket_number", ASCENDING)], unique=True, name="uq_support_tickets_number"),
            IndexModel([("user_id", ASCENDING), ("created_at", ASCENDING)], name="idx_support_tickets_user_created"),
            IndexModel([("status", ASCENDING)], name="idx_support_tickets_status"),
        ],
    )
