from __future__ import annotations

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[dict]):
    collection_name = "customers"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    async def list_by_restaurant(self, restaurant_id: str, page: int, page_size: int) -> tuple[list[dict], int]:
        return await self.get_multi(
            filters={"restaurant_id": ObjectId(restaurant_id)},
            page=page,
            page_size=page_size,
        )
