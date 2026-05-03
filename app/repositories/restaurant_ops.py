from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from app.core.exceptions import NotFoundException
from app.db.collections import RestaurantCollections
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
    collection_name = RestaurantCollections.INVOICES

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
        skip = (page - 1) * page_size
        pipeline: list[dict[str, Any]] = [
            {"$match": filters},
            {"$sort": {"invoice_date": DESCENDING, "created_at": DESCENDING}},
            {
                "$facet": {
                    "items": [
                        {"$skip": skip},
                        {"$limit": page_size},
                        {
                            "$project": {
                                "_id": 1,
                                "document_type": 1,
                                "document_label": 1,
                                "counterparty_name": 1,
                                "supplier_name": 1,
                                "invoice_number": 1,
                                "invoice_date": 1,
                                "upload_date": 1,
                                "total_amount": 1,
                                "currency": 1,
                                "expense_amount": 1,
                                "cash_amount": 1,
                                "revenue_amount": 1,
                                "profit_amount": 1,
                                "status": 1,
                                "created_by_user_id": 1,
                                "last_edited_by_user_id": 1,
                                "confirmed_at": 1,
                                "created_at": 1,
                                "updated_at": 1,
                                "line_item_count": {
                                    "$size": {"$ifNull": ["$line_items", []]},
                                },
                            }
                        },
                    ],
                    "total": [{"$count": "count"}],
                }
            },
        ]
        result = await self.aggregate(pipeline)
        facet = result[0] if result else {}
        items = facet.get("items", [])
        total_entries = facet.get("total", [])
        total = int(total_entries[0]["count"]) if total_entries else 0
        return items, total


class RestaurantExpenseRepository(ScopedRepository):
    collection_name = RestaurantCollections.EXPENSES

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

    async def find_inventory_linked_expense(self, *, scope_id: str, inventory_item_id: str) -> dict[str, Any] | None:
        return await self.get_one(
            self.scope_filters(
                scope_id,
                {
                    "source_kind": "inventory",
                    "source_inventory_item_id": inventory_item_id,
                },
            )
        )

    async def find_source_linked_expense(self, *, scope_id: str, source_kind: str, source_id: str) -> dict[str, Any] | None:
        return await self.get_one(
            self.scope_filters(
                scope_id,
                {
                    "source_kind": source_kind,
                    "source_id": source_id,
                },
            )
        )

    async def delete_source_linked_expenses(self, *, scope_id: str, source_kind: str, source_id: str) -> None:
        await self.collection.delete_many(
            self.scope_filters(
                scope_id,
                {
                    "source_kind": source_kind,
                    "source_id": source_id,
                },
            )
        )


class RestaurantCashDepositRepository(ScopedRepository):
    collection_name = RestaurantCollections.CASH_DEPOSITS

    async def list_by_scope(self, *, scope_id: str, page: int = 1, page_size: int = 20) -> tuple[list[dict[str, Any]], int]:
        return await self.get_multi(filters=self.scope_filters(scope_id), page=page, page_size=page_size)

    async def find_source_linked_deposit(
        self,
        *,
        scope_id: str,
        source_kind: str,
        source_id: str,
        source_subtype: str,
    ) -> dict[str, Any] | None:
        return await self.get_one(
            self.scope_filters(
                scope_id,
                {
                    "source_kind": source_kind,
                    "source_id": source_id,
                    "source_subtype": source_subtype,
                },
            )
        )

    async def delete_source_linked_deposits(self, *, scope_id: str, source_kind: str, source_id: str) -> None:
        await self.collection.delete_many(
            self.scope_filters(
                scope_id,
                {
                    "source_kind": source_kind,
                    "source_id": source_id,
                },
            )
        )

    async def delete_source_linked_deposit(
        self,
        *,
        scope_id: str,
        source_kind: str,
        source_id: str,
        source_subtype: str,
    ) -> None:
        await self.collection.delete_many(
            self.scope_filters(
                scope_id,
                {
                    "source_kind": source_kind,
                    "source_id": source_id,
                    "source_subtype": source_subtype,
                },
            )
        )


class RestaurantBankAccountRepository(ScopedRepository):
    collection_name = RestaurantCollections.BANK_ACCOUNTS

    async def list_by_scope(self, *, scope_id: str, page: int = 1, page_size: int = 100) -> tuple[list[dict[str, Any]], int]:
        return await self.get_multi(
            filters=self.scope_filters(scope_id),
            page=page,
            page_size=page_size,
            sort=[("bank_account", ASCENDING), ("created_at", DESCENDING)],
        )

    async def find_by_normalized_name(self, *, scope_id: str, normalized_name: str) -> dict[str, Any] | None:
        return await self.get_one(self.scope_filters(scope_id, {"normalized_name": normalized_name}))

    async def find_by_normalized_name_excluding_id(self, *, scope_id: str, normalized_name: str, exclude_id: str) -> dict[str, Any] | None:
        existing = await self.get_one(self.scope_filters(scope_id, {"normalized_name": normalized_name}))
        if existing and str(existing.get("_id")) != exclude_id:
            return existing
        return None


class RestaurantDailyRecordRepository(ScopedRepository):
    collection_name = RestaurantCollections.MANUAL_ENTRIES

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
                date_filters["$gte"] = start_date.isoformat()
            if end_date:
                date_filters["$lte"] = end_date.isoformat()
            filters["business_date"] = date_filters
        return await self.get_multi(
            filters=filters,
            page=page,
            page_size=page_size,
            sort=[("business_date", DESCENDING), ("created_at", DESCENDING)],
        )

    async def find_by_business_date(self, *, scope_id: str, business_date: date) -> dict[str, Any] | None:
        return await self.get_one(self.scope_filters(scope_id, {"business_date": business_date.isoformat()}))


class RestaurantRecordRepository(ScopedRepository):
    collection_name = RestaurantCollections.FINANCE_SNAPSHOTS

    async def list_by_scope(
        self,
        *,
        scope_id: str,
        page: int = 1,
        page_size: int = 20,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        filters = self.scope_filters(scope_id, {"period_type": "day"})
        if start_date or end_date:
            date_filters: dict[str, Any] = {}
            if start_date:
                date_filters["$gte"] = start_date.isoformat()
            if end_date:
                date_filters["$lte"] = end_date.isoformat()
            filters["period_start_date"] = date_filters
        return await self.get_multi(filters=filters, page=page, page_size=page_size, sort=[("period_start_date", DESCENDING), ("updated_at", DESCENDING)])

    async def find_by_business_date(self, *, scope_id: str, business_date: date) -> dict[str, Any] | None:
        return await self.get_one(self.scope_filters(scope_id, {"period_type": "day", "period_key": business_date.isoformat()}))

    async def upsert_by_business_date(self, *, scope_id: str, business_date: date, payload: dict[str, Any]) -> dict[str, Any]:
        existing = await self.find_by_business_date(scope_id=scope_id, business_date=business_date)
        if existing:
            return await self.update(existing["_id"], payload)
        return await self.create(
            {
                **payload,
                "tenant_id": scope_id,
                "period_type": "day",
                "period_key": business_date.isoformat(),
                "period_start_date": business_date.isoformat(),
                "period_end_date": business_date.isoformat(),
                "business_date": business_date.isoformat(),
            }
        )


class RestaurantWeeklyRecordRepository(ScopedRepository):
    collection_name = RestaurantCollections.FINANCE_SNAPSHOTS

    async def list_by_scope(self, *, scope_id: str, page: int = 1, page_size: int = 20) -> tuple[list[dict[str, Any]], int]:
        return await self.get_multi(
            filters=self.scope_filters(scope_id, {"period_type": "week"}),
            page=page,
            page_size=page_size,
            sort=[("period_start_date", DESCENDING), ("updated_at", DESCENDING)],
        )

    async def find_by_week_start_date(self, *, scope_id: str, week_start_date: date) -> dict[str, Any] | None:
        return await self.get_one(self.scope_filters(scope_id, {"period_type": "week", "period_key": week_start_date.isoformat()}))

    async def upsert_by_week_start_date(self, *, scope_id: str, week_start_date: date, payload: dict[str, Any]) -> dict[str, Any]:
        existing = await self.find_by_week_start_date(scope_id=scope_id, week_start_date=week_start_date)
        if existing:
            return await self.update(existing["_id"], payload)
        week_end_date = payload.get("week_end_date", week_start_date.isoformat())
        return await self.create(
            {
                **payload,
                "tenant_id": scope_id,
                "period_type": "week",
                "period_key": week_start_date.isoformat(),
                "period_start_date": week_start_date.isoformat(),
                "period_end_date": week_end_date,
                "week_start_date": week_start_date.isoformat(),
            }
        )


class RestaurantMonthlyRecordRepository(ScopedRepository):
    collection_name = RestaurantCollections.FINANCE_SNAPSHOTS

    async def list_by_scope(self, *, scope_id: str, page: int = 1, page_size: int = 20) -> tuple[list[dict[str, Any]], int]:
        return await self.get_multi(
            filters=self.scope_filters(scope_id, {"period_type": "month"}),
            page=page,
            page_size=page_size,
            sort=[("period_start_date", DESCENDING), ("updated_at", DESCENDING)],
        )

    async def find_by_month_key(self, *, scope_id: str, month_key: str) -> dict[str, Any] | None:
        return await self.get_one(self.scope_filters(scope_id, {"period_type": "month", "period_key": month_key}))

    async def upsert_by_month_key(self, *, scope_id: str, month_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        existing = await self.find_by_month_key(scope_id=scope_id, month_key=month_key)
        if existing:
            return await self.update(existing["_id"], payload)
        return await self.create(
            {
                **payload,
                "tenant_id": scope_id,
                "period_type": "month",
                "period_key": month_key,
                "period_start_date": str(payload.get("month_start_date") or month_key),
                "period_end_date": str(payload.get("month_end_date") or month_key),
                "month_key": month_key,
            }
        )


class RestaurantInventoryRepository(ScopedRepository):
    collection_name = RestaurantCollections.INVENTORY_ITEMS

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


class RestaurantInventoryCategoryRepository(ScopedRepository):
    collection_name = RestaurantCollections.INVENTORY_CATEGORIES

    async def list_by_scope(self, *, scope_id: str, limit: int = 100) -> list[dict[str, Any]]:
        cursor = self.collection.find(self.scope_filters(scope_id)).sort([("name", ASCENDING)]).limit(limit)
        return await cursor.to_list(length=limit)

    async def find_by_normalized_name(self, *, scope_id: str, normalized_name: str) -> dict[str, Any] | None:
        return await self.get_one(self.scope_filters(scope_id, {"normalized_name": normalized_name}))


class RestaurantInventorySupplierRepository(ScopedRepository):
    collection_name = RestaurantCollections.INVENTORY_SUPPLIERS

    async def list_by_scope(self, *, scope_id: str, limit: int = 100) -> list[dict[str, Any]]:
        cursor = self.collection.find(self.scope_filters(scope_id)).sort([("name", ASCENDING)]).limit(limit)
        return await cursor.to_list(length=limit)

    async def find_by_normalized_name(self, *, scope_id: str, normalized_name: str) -> dict[str, Any] | None:
        return await self.get_one(self.scope_filters(scope_id, {"normalized_name": normalized_name}))


class RestaurantChatRepository(ScopedRepository):
    collection_name = RestaurantCollections.CHAT_MESSAGES

    async def list_recent_by_scope(self, *, scope_id: str, limit: int = 20) -> list[dict[str, Any]]:
        cursor = self.collection.find(self.scope_filters(scope_id)).sort([("created_at", ASCENDING)]).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_by_scope_and_id(self, *, scope_id: str, message_id: str) -> dict[str, Any]:
        document = await self.get_optional_by_id(message_id)
        if not document or document.get("tenant_id") != scope_id:
            raise NotFoundException("Chat message not found")
        return document


class RestaurantInsightRepository(ScopedRepository):
    collection_name = RestaurantCollections.AI_INSIGHTS

    async def list_by_scope(self, *, scope_id: str, limit: int = 10) -> list[dict[str, Any]]:
        cursor = self.collection.find(self.scope_filters(scope_id)).sort([("created_at", DESCENDING)]).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_by_scope_and_id(self, *, scope_id: str, insight_id: str) -> dict[str, Any]:
        document = await self.get_optional_by_id(insight_id)
        if not document or document.get("tenant_id") != scope_id:
            raise NotFoundException("Insight not found")
        return document


class RestaurantFinanceTransactionRepository(ScopedRepository):
    collection_name = RestaurantCollections.FINANCE_TRANSACTIONS

    async def list_by_scope(
        self,
        *,
        scope_id: str,
        page: int = 1,
        page_size: int = 100,
        start_date: date | None = None,
        end_date: date | None = None,
        transaction_type: str | None = None,
        source_kind: str | None = None,
        source_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        filters = self.scope_filters(scope_id)
        if start_date or end_date:
            date_filters: dict[str, Any] = {}
            if start_date:
                date_filters["$gte"] = start_date.isoformat()
            if end_date:
                date_filters["$lte"] = end_date.isoformat()
            filters["business_date"] = date_filters
        if transaction_type:
            filters["transaction_type"] = transaction_type
        if source_kind:
            filters["source_kind"] = source_kind
        if source_id:
            filters["source_id"] = source_id
        return await self.get_multi(filters=filters, page=page, page_size=page_size, sort=[("business_date", DESCENDING), ("created_at", DESCENDING)])

    async def replace_for_source(self, *, scope_id: str, source_kind: str, source_id: str, transactions: list[dict[str, Any]]) -> None:
        await self.collection.delete_many(self.scope_filters(scope_id, {"source_kind": source_kind, "source_id": source_id}))
        if not transactions:
            return
        await self.collection.insert_many(transactions)

    async def delete_for_source(self, *, scope_id: str, source_kind: str, source_id: str) -> None:
        await self.collection.delete_many(self.scope_filters(scope_id, {"source_kind": source_kind, "source_id": source_id}))
