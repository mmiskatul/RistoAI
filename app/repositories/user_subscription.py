from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class UserSubscriptionRepository(BaseRepository[dict]):
    collection_name = "user_subscriptions"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    async def get_by_user_id(self, user_id: str) -> list[dict]:
        return await self.collection.find(
            {"user_id": self.to_object_id(user_id)},
            sort=[("created_at", -1)],
        ).to_list(length=None)
