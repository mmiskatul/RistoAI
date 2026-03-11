from __future__ import annotations

from datetime import timedelta
from hashlib import sha256

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

from app.repositories.base import BaseRepository
from app.utils.datetime import utc_now


class AuthCodeRepository(BaseRepository[dict]):
    collection_name = "auth_codes"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    @staticmethod
    def hash_code(*, email: str, purpose: str, code: str) -> str:
        return sha256(f"{email.lower()}:{purpose}:{code}".encode("utf-8")).hexdigest()

    async def create_code(self, *, user_id, email: str, purpose: str, code: str, expires_in_seconds: int) -> dict:
        await self.collection.update_many(
            {"email": email.lower(), "purpose": purpose, "consumed_at": None},
            {"$set": {"consumed_at": utc_now(), "updated_at": utc_now()}},
        )
        return await self.create(
            {
                "user_id": user_id,
                "email": email.lower(),
                "purpose": purpose,
                "code_hash": self.hash_code(email=email, purpose=purpose, code=code),
                "expires_at": utc_now() + timedelta(seconds=expires_in_seconds),
                "consumed_at": None,
            }
        )

    async def verify_code(self, *, email: str, purpose: str, code: str) -> dict | None:
        return await self.collection.find_one(
            {
                "email": email.lower(),
                "purpose": purpose,
                "code_hash": self.hash_code(email=email, purpose=purpose, code=code),
                "consumed_at": None,
                "expires_at": {"$gt": utc_now()},
            },
            sort=[("created_at", DESCENDING)],
        )

    async def consume_code(self, code_id) -> None:
        await self.collection.update_one(
            {"_id": self.to_object_id(code_id)},
            {"$set": {"consumed_at": utc_now(), "updated_at": utc_now()}},
        )

    async def count_pending(self, *, purpose: str | None = None) -> int:
        filters = {
            "consumed_at": None,
            "expires_at": {"$gt": utc_now()},
        }
        if purpose:
            filters["purpose"] = purpose
        return await self.count(filters)
