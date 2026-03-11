from __future__ import annotations

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class MenuCategoryRepository(BaseRepository[dict]):
    collection_name = "menu_categories"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    async def list_by_restaurant(self, restaurant_id: str, page: int, page_size: int) -> tuple[list[dict], int]:
        return await self.get_multi(
            filters={"restaurant_id": ObjectId(restaurant_id)},
            page=page,
            page_size=page_size,
        )


class MenuItemRepository(BaseRepository[dict]):
    collection_name = "menu_items"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    async def list_by_restaurant(
        self,
        restaurant_id: str,
        page: int,
        page_size: int,
        branch_id: str | None = None,
    ) -> tuple[list[dict], int]:
        filters: dict = {"restaurant_id": ObjectId(restaurant_id)}
        if branch_id:
            filters["branch_id"] = ObjectId(branch_id)
        return await self.get_multi(filters=filters, page=page, page_size=page_size)

    async def get_by_ids(self, item_ids: list[str]) -> list[dict]:
        return await self.collection.find({"_id": {"$in": [ObjectId(item_id) for item_id in item_ids]}}).to_list(length=None)
