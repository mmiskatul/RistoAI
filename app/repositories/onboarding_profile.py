from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.repositories.base import BaseRepository
from app.utils.datetime import utc_now


class OnboardingProfileRepository(BaseRepository[dict]):
    collection_name = "onboarding_profiles"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    async def get_by_user_id(self, user_id: str) -> dict | None:
        return await self.get_one({"user_id": user_id})

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
