from __future__ import annotations

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class OrderRepository(BaseRepository[dict]):
    collection_name = "orders"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db)

    async def list_by_restaurant(
        self,
        restaurant_id: str,
        page: int,
        page_size: int,
        branch_id: str | None = None,
    ) -> tuple[list[dict], int]:
        filters: dict = {"restaurant_id": ObjectId(restaurant_id)}
        if branch_id:
            filters["branch_id"] = ObjectId(branch_id)
        return await self.get_multi(filters=filters, page=page, page_size=page_size)

    async def sales_summary(self, restaurant_id: str) -> dict:
        pipeline = [
            {"$match": {"restaurant_id": ObjectId(restaurant_id), "order_status": {"$ne": "cancelled"}}},
            {
                "$group": {
                    "_id": None,
                    "total_sales": {"$sum": "$total"},
                    "total_orders": {"$sum": 1},
                    "average_order_value": {"$avg": "$total"},
                }
            },
        ]
        result = await self.aggregate(pipeline)
        return result[0] if result else {"total_sales": 0.0, "total_orders": 0, "average_order_value": 0.0}

    async def status_breakdown(self, restaurant_id: str) -> dict[str, int]:
        pipeline = [
            {"$match": {"restaurant_id": ObjectId(restaurant_id)}},
            {"$group": {"_id": "$order_status", "count": {"$sum": 1}}},
        ]
        rows = await self.aggregate(pipeline)
        return {row["_id"]: row["count"] for row in rows}

    async def menu_performance(self, restaurant_id: str, limit: int = 5) -> list[dict]:
        pipeline = [
            {"$match": {"restaurant_id": ObjectId(restaurant_id), "order_status": {"$ne": "cancelled"}}},
            {"$unwind": "$items"},
            {
                "$group": {
                    "_id": "$items.menu_item_id",
                    "name": {"$first": "$items.name"},
                    "quantity_sold": {"$sum": "$items.quantity"},
                    "revenue": {"$sum": "$items.line_total"},
                }
            },
            {"$sort": {"revenue": -1}},
            {"$limit": limit},
        ]
        return await self.aggregate(pipeline)
