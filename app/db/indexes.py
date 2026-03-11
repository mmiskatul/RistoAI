from __future__ import annotations

from pymongo import ASCENDING, IndexModel

from motor.motor_asyncio import AsyncIOMotorDatabase


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create essential indexes for auth-related collections."""
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
