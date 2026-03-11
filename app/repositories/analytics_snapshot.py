from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class AnalyticsSnapshotRepository(BaseRepository[dict]):
    collection_name = "analytics_snapshots"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)
