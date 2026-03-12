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

    async def get_filtered_users(
        self,
        *,
        search: str | None = None,
        role: UserRole | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, object]], int]:
        filters: dict[str, object] = {}
        and_filters: list[dict[str, object]] = []

        if role is not None:
            and_filters.append({"role": role})
        if is_active is not None:
            and_filters.append({"is_active": is_active})
        if search:
            escaped_search = {"$regex": search.strip(), "$options": "i"}
            and_filters.append(
                {
                    "$or": [
                        {"full_name": escaped_search},
                        {"email": escaped_search},
                        {"phone": escaped_search},
                    ]
                }
            )
        if and_filters:
            filters = {"$and": and_filters} if len(and_filters) > 1 else and_filters[0]

        return await self.get_multi(filters=filters, page=page, page_size=page_size)
