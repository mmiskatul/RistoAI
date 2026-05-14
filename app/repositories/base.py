from __future__ import annotations

from abc import ABC
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import DESCENDING, ReturnDocument

from app.core.exceptions import NotFoundException
from app.utils.datetime import utc_now

DocumentType = TypeVar("DocumentType")


class BaseRepository(ABC, Generic[DocumentType]):
    """Repository Pattern: shared async CRUD operations for MongoDB collections."""

    collection_name: str

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.collection: AsyncIOMotorCollection = db[self.collection_name]

    @staticmethod
    def to_object_id(value: str | ObjectId) -> ObjectId:
        if isinstance(value, ObjectId):
            return value
        return ObjectId(value)

    async def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        payload.setdefault("created_at", now)
        payload["updated_at"] = now
        result = await self.collection.insert_one(payload)
        return await self.get_by_id(result.inserted_id)

    async def get_by_id(
        self,
        document_id: str | ObjectId,
        *,
        projection: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        document = await self.collection.find_one({"_id": self.to_object_id(document_id)}, projection)
        if not document:
            raise NotFoundException(f"{self.collection_name.rstrip('s').replace('_', ' ').title()} not found")
        return document

    async def get_optional_by_id(
        self,
        document_id: str | ObjectId,
        *,
        projection: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        return await self.collection.find_one({"_id": self.to_object_id(document_id)}, projection)

    async def get_one(
        self,
        filters: dict[str, Any],
        *,
        projection: dict[str, Any] | None = None,
        sort: list[tuple[str, int]] | None = None,
    ) -> dict[str, Any] | None:
        return await self.collection.find_one(filters, projection, sort=sort)

    async def get_multi(
        self,
        *,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
        sort: list[tuple[str, int]] | None = None,
        projection: dict[str, Any] | None = None,
        count_total: bool = True,
    ) -> tuple[list[dict[str, Any]], int]:
        resolved_filters = filters or {}
        resolved_sort = sort or [("created_at", DESCENDING)]
        skip = (page - 1) * page_size
        cursor = self.collection.find(resolved_filters, projection).sort(resolved_sort).skip(skip).limit(page_size)
        items = await cursor.to_list(length=page_size)
        total = await self.collection.count_documents(resolved_filters) if count_total else len(items)
        return items, total

    async def list_all(
        self,
        *,
        filters: dict[str, Any] | None = None,
        sort: list[tuple[str, int]] | None = None,
        projection: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        resolved_filters = filters or {}
        resolved_sort = sort or [("created_at", DESCENDING)]
        cursor = self.collection.find(resolved_filters, projection).sort(resolved_sort).limit(limit)
        return await cursor.to_list(length=limit)

    async def update(self, document_id: str | ObjectId, payload: dict[str, Any]) -> dict[str, Any]:
        payload["updated_at"] = utc_now()
        result = await self.collection.find_one_and_update(
            {"_id": self.to_object_id(document_id)},
            {"$set": payload},
            return_document=ReturnDocument.AFTER,
        )
        if not result:
            raise NotFoundException(f"{self.collection_name.rstrip('s').replace('_', ' ').title()} not found")
        return result

    async def delete(self, document_id: str | ObjectId) -> None:
        result = await self.collection.delete_one({"_id": self.to_object_id(document_id)})
        if result.deleted_count == 0:
            raise NotFoundException(f"{self.collection_name.rstrip('s').replace('_', ' ').title()} not found")

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        return await self.collection.count_documents(filters or {})

    async def aggregate(self, pipeline: list[dict[str, Any]], *, limit: int | None = None) -> list[dict[str, Any]]:
        return await self.collection.aggregate(pipeline).to_list(length=limit)

    async def get_monthly_counts(
        self,
        *,
        year: int,
        filters: dict[str, Any] | None = None,
        date_field: str = "created_at",
    ) -> list[int]:
        start = datetime(year, 1, 1, tzinfo=UTC)
        end = datetime(year + 1, 1, 1, tzinfo=UTC)
        pipeline = [
            {
                "$match": {
                    **(filters or {}),
                    date_field: {"$gte": start, "$lt": end},
                }
            },
            {
                "$group": {
                    "_id": {"$month": f"${date_field}"},
                    "count": {"$sum": 1},
                }
            },
        ]
        counts = [0] * 12
        for row in await self.aggregate(pipeline):
            counts[row["_id"] - 1] = row["count"]
        return counts
