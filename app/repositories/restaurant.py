from __future__ import annotations

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class RestaurantRepository(BaseRepository[dict]):
    collection_name = "restaurants"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    async def list_by_owner(self, owner_id: str | ObjectId, page: int, page_size: int) -> tuple[list[dict], int]:
        return await self.get_multi(
            filters={"owner_id": self.to_object_id(owner_id)},
            page=page,
            page_size=page_size,
        )

    async def list_by_ids(self, restaurant_ids: list[str], page: int, page_size: int) -> tuple[list[dict], int]:
        return await self.get_multi(
            filters={"_id": {"$in": [self.to_object_id(item) for item in restaurant_ids]}},
            page=page,
            page_size=page_size,
        )
