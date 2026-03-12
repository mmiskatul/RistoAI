from __future__ import annotations

from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.enums import CouponStatus
from app.repositories.base import BaseRepository


class CouponRepository(BaseRepository[dict]):
    collection_name = "coupons"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    async def get_by_code(self, code: str) -> dict | None:
        return await self.get_one({"code": code.upper()})

    async def get_filtered_coupons(
        self,
        *,
        search: str | None = None,
        status: CouponStatus | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        filters: dict[str, object] = {}
        and_filters: list[dict[str, object]] = []
        if status is not None:
            and_filters.append({"status": status})
        if search:
            and_filters.append({"code": {"$regex": search.strip(), "$options": "i"}})
        if and_filters:
            filters = {"$and": and_filters} if len(and_filters) > 1 else and_filters[0]
        return await self.get_multi(filters=filters, page=page, page_size=page_size)

    async def mark_expired_coupons(self) -> None:
        await self.collection.update_many(
            {
                "expires_at": {"$lt": datetime.now(UTC)},
                "status": {"$ne": CouponStatus.EXPIRED},
            },
            {"$set": {"status": CouponStatus.EXPIRED}},
        )
