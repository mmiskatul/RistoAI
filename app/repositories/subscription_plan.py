from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class SubscriptionPlanRepository(BaseRepository[dict]):
    collection_name = "subscription_plans"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    async def get_by_name(self, name: str) -> dict | None:
        return await self.get_one({"name": name})

    async def get_active_plans(self) -> list[dict]:
        return await self.collection.find({"is_active": True}).sort("monthly_price", 1).to_list(length=None)

    async def get_visible_plans(self) -> list[dict]:
        return await self.collection.find({"is_active": True, "is_visible": True}).sort("monthly_price", 1).to_list(length=None)
