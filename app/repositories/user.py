from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[dict]):
    collection_name = "users"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    async def get_by_email(self, email: str) -> dict | None:
        return await self.get_one({"email": email.lower()})
