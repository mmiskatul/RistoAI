from __future__ import annotations

from app.repositories.analytics_snapshot import AnalyticsSnapshotRepository
from app.repositories.customer import CustomerRepository
from app.repositories.menu import MenuItemRepository
from app.repositories.order import OrderRepository
from app.schemas.analytics import (
    DashboardSummary,
    MenuPerformanceItem,
    MenuPerformanceResponse,
    OrdersAnalyticsResponse,
    SalesAnalyticsResponse,
)
from app.services.base import BaseService
from app.utils.datetime import utc_now


class AnalyticsService(BaseService):
    def __init__(
        self,
        order_repository: OrderRepository,
        menu_item_repository: MenuItemRepository,
        customer_repository: CustomerRepository,
        snapshot_repository: AnalyticsSnapshotRepository,
    ) -> None:
        self.order_repository = order_repository
        self.menu_item_repository = menu_item_repository
        self.customer_repository = customer_repository
        self.snapshot_repository = snapshot_repository

    async def dashboard_summary(self, current_user: dict, restaurant_id: str) -> DashboardSummary:
        self.ensure_restaurant_access(current_user, restaurant_id)
        sales = await self.order_repository.sales_summary(restaurant_id)
        total_customers = await self.customer_repository.count({"restaurant_id": self.customer_repository.to_object_id(restaurant_id)})
        active_menu_items = await self.menu_item_repository.count(
            {"restaurant_id": self.menu_item_repository.to_object_id(restaurant_id), "availability": True},
        )
        return DashboardSummary(
            total_orders=sales.get("total_orders", 0),
            total_revenue=round(sales.get("total_sales", 0.0), 2),
            active_menu_items=active_menu_items,
            total_customers=total_customers,
            average_order_value=round(sales.get("average_order_value", 0.0), 2),
        )

    async def sales_analytics(self, current_user: dict, restaurant_id: str) -> SalesAnalyticsResponse:
        self.ensure_restaurant_access(current_user, restaurant_id)
        sales = await self.order_repository.sales_summary(restaurant_id)
        response = SalesAnalyticsResponse(
            restaurant_id=restaurant_id,
            period="lifetime",
            total_sales=round(sales.get("total_sales", 0.0), 2),
            total_orders=sales.get("total_orders", 0),
            average_order_value=round(sales.get("average_order_value", 0.0), 2),
        )
        await self.snapshot_repository.create(
            {
                "restaurant_id": self.snapshot_repository.to_object_id(restaurant_id),
                "metric_type": "sales",
                "payload": response.model_dump(),
                "period_start": None,
                "period_end": None,
                "generated_at": utc_now().isoformat(),
            }
        )
        return response

    async def orders_analytics(self, current_user: dict, restaurant_id: str) -> OrdersAnalyticsResponse:
        self.ensure_restaurant_access(current_user, restaurant_id)
        breakdown = await self.order_repository.status_breakdown(restaurant_id)
        total_orders = sum(breakdown.values())
        return OrdersAnalyticsResponse(restaurant_id=restaurant_id, by_status=breakdown, total_orders=total_orders)

    async def menu_performance(self, current_user: dict, restaurant_id: str) -> MenuPerformanceResponse:
        self.ensure_restaurant_access(current_user, restaurant_id)
        rows = await self.order_repository.menu_performance(restaurant_id)
        top_items = [
            MenuPerformanceItem(
                menu_item_id=str(row["_id"]),
                name=row["name"],
                quantity_sold=row["quantity_sold"],
                revenue=round(row["revenue"], 2),
            )
            for row in rows
        ]
        return MenuPerformanceResponse(restaurant_id=restaurant_id, top_items=top_items)
