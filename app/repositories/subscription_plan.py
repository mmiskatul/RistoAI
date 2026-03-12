from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.exceptions import NotFoundException
from app.repositories.base import BaseRepository


class SubscriptionPlanRepository(BaseRepository[dict]):
    collection_name = "subscription_plan"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    async def get_plan(self) -> dict:
        plan = await self.get_optional_plan()
        if not plan:
            raise NotFoundException('Subscription plan not found')
        return plan

    async def get_optional_plan(self) -> dict | None:
        return await self.collection.find_one({}, sort=[('created_at', 1)])

    async def get_active_plans(self) -> list[dict]:
        plan = await self.collection.find_one({'is_active': True}, sort=[('created_at', 1)])
        return [plan] if plan else []

    async def get_visible_plans(self) -> list[dict]:
        plan = await self.collection.find_one({'is_active': True, 'is_visible': True}, sort=[('created_at', 1)])
        return [plan] if plan else []
