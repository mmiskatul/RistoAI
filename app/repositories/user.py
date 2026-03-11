from __future__ import annotations

from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.enums import UserRole
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[dict]):
    collection_name = "users"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    async def get_by_email(self, email: str) -> dict | None:
        return await self.get_one({"email": email.lower()})

    async def get_role_counts(self) -> dict[str, int]:
        pipeline = [
            {"$group": {"_id": "$role", "count": {"$sum": 1}}},
        ]
        rows = await self.aggregate(pipeline)
        return {str(row["_id"]): row["count"] for row in rows}

    async def count_by_role(self, role: UserRole) -> int:
        return await self.count({"role": role})

    async def get_monthly_registrations(self, year: int) -> list[int]:
        return await self.get_monthly_counts(year=year)

    async def count_new_users_in_month(self, year: int, month: int) -> int:
        start = datetime(year, month, 1, tzinfo=UTC)
        end = datetime(year + (month // 12), (month % 12) + 1, 1, tzinfo=UTC)
        return await self.count({"created_at": {"$gte": start, "$lt": end}})
