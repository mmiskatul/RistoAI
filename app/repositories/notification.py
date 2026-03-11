from __future__ import annotations

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[dict]):
    collection_name = "notifications"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    async def list_for_user(self, user_id: str, page: int, page_size: int) -> tuple[list[dict], int]:
        return await self.get_multi(
            filters={"user_id": ObjectId(user_id)},
            page=page,
            page_size=page_size,
        )
