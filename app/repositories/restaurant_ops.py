from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from app.core.exceptions import NotFoundException
from app.repositories.base import BaseRepository


class ScopedRepository(BaseRepository[dict]):
    scope_field = "tenant_id"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    @staticmethod
    def resolve_scope_id(current_user: dict) -> str:
        return str(current_user.get("organization_id") or current_user["_id"])

    def scope_filters(self, scope_id: str, extra_filters: dict[str, Any] | None = None) -> dict[str, Any]:
        filters: dict[str, Any] = {self.scope_field: scope_id}
        if extra_filters:
            filters.update(extra_filters)
        return filters

    async def get_scoped_by_id(self, document_id: str, scope_id: str) -> dict[str, Any]:
        document = await self.get_optional_by_id(document_id)
        if not document or document.get(self.scope_field) != scope_id:
            raise NotFoundException(f"{self.collection_name.rstrip('s').replace('_', ' ').title()} not found")
        return document


class RestaurantDocumentRepository(ScopedRepository):
    collection_name = "restaurant_documents"

    async def list_by_scope(
        self,
        *,
        scope_id: str,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        search: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        filters: dict[str, Any] = self.scope_filters(scope_id)
        if status:
            filters["status"] = status
        if search:
            regex = {"$regex": search.strip(), "$options": "i"}
            filters["$or"] = [
                {"supplier_name": regex},
                {"invoice_number": regex},
                {"source_file_name": regex},
            ]
        return await self.get_multi(filters=filters, page=page, page_size=page_size, sort=[("invoice_date", DESCENDING), ("created_at", DESCENDING)])


class RestaurantExpenseRepository(ScopedRepository):
    collection_name = "restaurant_expenses"

    async def list_by_scope(
        self,
        *,
        scope_id: str,
        page: int = 1,
        page_size: int = 20,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        filters = self.scope_filters(scope_id)
        if start_date or end_date:
            date_filters: dict[str, Any] = {}
            if start_date:
                date_filters["$gte"] = datetime.combine(start_date, time.min, tzinfo=UTC)
            if end_date:
                date_filters["$lte"] = datetime.combine(end_date, time.max, tzinfo=UTC)
            filters["expense_date"] = date_filters
        return await self.get_multi(filters=filters, page=page, page_size=page_size)


class RestaurantCashDepositRepository(ScopedRepository):
    collection_name = "restaurant_cash_deposits"

    async def list_by_scope(self, *, scope_id: str, page: int = 1, page_size: int = 20) -> tuple[list[dict[str, Any]], int]:
        return await self.get_multi(filters=self.scope_filters(scope_id), page=page, page_size=page_size)


class RestaurantDailyRecordRepository(ScopedRepository):
    collection_name = "restaurant_daily_records"

    async def list_by_scope(
        self,
        *,
        scope_id: str,
        page: int = 1,
        page_size: int = 20,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        filters = self.scope_filters(scope_id)
        if start_date or end_date:
            date_filters: dict[str, Any] = {}
            if start_date:
                date_filters["$gte"] = start_date
            if end_date:
                date_filters["$lte"] = end_date
            filters["business_date"] = date_filters
        return await self.get_multi(
            filters=filters,
            page=page,
            page_size=page_size,
            sort=[("business_date", DESCENDING), ("created_at", DESCENDING)],
        )

    async def find_by_business_date(self, *, scope_id: str, business_date: date) -> dict[str, Any] | None:
        return await self.get_one(self.scope_filters(scope_id, {"business_date": business_date}))


class RestaurantInventoryRepository(ScopedRepository):
    collection_name = "restaurant_inventory_items"

    async def list_by_scope(
        self,
        *,
        scope_id: str,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        status: str | None = None,
        category: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        filters = self.scope_filters(scope_id)
        if search:
            regex = {"$regex": search.strip(), "$options": "i"}
            filters["$or"] = [
                {"product_name": regex},
                {"supplier_name": regex},
                {"category": regex},
            ]
        if status:
            filters["stock_status"] = status
        if category:
            filters["category"] = category
        return await self.get_multi(filters=filters, page=page, page_size=page_size)


class RestaurantChatRepository(ScopedRepository):
    collection_name = "restaurant_chat_messages"

    async def list_recent_by_scope(self, *, scope_id: str, limit: int = 20) -> list[dict[str, Any]]:
        cursor = self.collection.find(self.scope_filters(scope_id)).sort([("created_at", ASCENDING)]).limit(limit)
        return await cursor.to_list(length=limit)


class RestaurantInsightRepository(ScopedRepository):
    collection_name = "restaurant_ai_insights"

    async def list_by_scope(self, *, scope_id: str, limit: int = 10) -> list[dict[str, Any]]:
        cursor = self.collection.find(self.scope_filters(scope_id)).sort([("created_at", DESCENDING)]).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_by_scope_and_id(self, *, scope_id: str, insight_id: str) -> dict[str, Any]:
        document = await self.get_optional_by_id(insight_id)
        if not document or document.get("tenant_id") != scope_id:
            raise NotFoundException("Insight not found")
        return document
