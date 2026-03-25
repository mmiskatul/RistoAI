from __future__ import annotations

from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.enums import SubscriptionStatus
from app.db.collections import CoreCollections
from app.repositories.base import BaseRepository
from app.utils.datetime import utc_now


class UserSubscriptionRepository(BaseRepository[dict]):
    collection_name = CoreCollections.USER_SUBSCRIPTIONS

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    async def get_by_user_id(self, user_id: str) -> list[dict]:
        return await self.collection.find(
            {"user_id": self.to_object_id(user_id)},
            sort=[("created_at", -1)],
        ).to_list(length=None)

    async def get_current_by_user_id(self, user_id: str) -> dict | None:
        return await self.collection.find_one(
            {"user_id": self.to_object_id(user_id), "is_current": True},
            sort=[("created_at", -1)],
        )

    async def close_current_for_user(
        self,
        user_id: str,
        *,
        ended_at: datetime | None = None,
        final_status: SubscriptionStatus = SubscriptionStatus.CANCELED,
    ) -> None:
        resolved_ended_at = ended_at or utc_now()
        await self.collection.update_many(
            {"user_id": self.to_object_id(user_id), "is_current": True},
            {
                "$set": {
                    "is_current": False,
                    "ended_at": resolved_ended_at,
                    "status": final_status,
                    "updated_at": resolved_ended_at,
                }
            },
        )
