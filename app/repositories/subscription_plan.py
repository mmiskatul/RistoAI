from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.exceptions import NotFoundException
from app.db.collections import CoreCollections
from app.repositories.base import BaseRepository


class SubscriptionPlanRepository(BaseRepository[dict]):
    collection_name = CoreCollections.SUBSCRIPTION_PLANS

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    async def get_plan(self) -> dict:
        plan = await self.get_optional_plan()
        if not plan:
            raise NotFoundException('Subscription plan not found')
        return plan

    async def get_optional_plan(self) -> dict | None:
        return await self.collection.find_one({}, sort=[('created_at', 1)])

    async def get_plans(self) -> list[dict]:
        return await self.collection.find().sort([('is_best_plan', -1), ('created_at', 1)]).to_list(length=100)

    async def get_active_plans(self) -> list[dict]:
        return await self.collection.find({'is_active': True}).sort([('is_best_plan', -1), ('created_at', 1)]).to_list(length=100)

    async def get_visible_plans(self) -> list[dict]:
        return await self.collection.find({'is_active': True, 'is_visible': True}).sort([('is_best_plan', -1), ('created_at', 1)]).to_list(length=100)
