from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.db.collections import CoreCollections
from app.repositories.base import BaseRepository
from app.utils.datetime import utc_now


class OnboardingProfileRepository(BaseRepository[dict]):
    collection_name = CoreCollections.ONBOARDING_PROFILES

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    async def get_by_user_id(self, user_id: str) -> dict | None:
        return await self.get_one({"user_id": user_id})

    async def get_by_user_ids(self, user_ids: list[str]) -> list[dict]:
        if not user_ids:
            return []
        return await self.collection.find({"user_id": {"$in": user_ids}}).to_list(length=len(user_ids))

    async def upsert_by_user_id(self, user_id: str, payload: dict) -> dict:
        now = utc_now()
        result = await self.collection.find_one_and_update(
            {"user_id": user_id},
            {
                "$set": {
                    **payload,
                    "user_id": user_id,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return result

    async def count_completed(self) -> int:
        return await self.count({"onboarding_completed": True})

    async def get_monthly_completed_counts(self, year: int) -> list[int]:
        return await self.get_monthly_counts(year=year, filters={"onboarding_completed": True})

    async def delete_by_user_id(self, user_id: str) -> None:
        await self.collection.delete_many({"user_id": user_id})
