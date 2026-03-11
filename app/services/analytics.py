from __future__ import annotations

from app.schemas.analytics import (
    DashboardSummary,
    MenuPerformanceItem,
    MenuPerformanceResponse,
    OrdersAnalyticsResponse,
    SalesAnalyticsResponse,
)
from app.services.base import BaseService


class AnalyticsService(BaseService):
    """Mock analytics service retained after restaurant/order domain removal."""

    async def dashboard_summary(self, current_user: dict, restaurant_id: str) -> DashboardSummary:
        return DashboardSummary(
            total_orders=0,
            total_revenue=0.0,
            active_menu_items=0,
            total_customers=0,
            average_order_value=0.0,
        )

    async def sales_analytics(self, current_user: dict, restaurant_id: str) -> SalesAnalyticsResponse:
        return SalesAnalyticsResponse(
            restaurant_id=restaurant_id,
            period="lifetime",
            total_sales=0.0,
            total_orders=0,
            average_order_value=0.0,
        )

    async def orders_analytics(self, current_user: dict, restaurant_id: str) -> OrdersAnalyticsResponse:
        return OrdersAnalyticsResponse(restaurant_id=restaurant_id, by_status={}, total_orders=0)

    async def menu_performance(self, current_user: dict, restaurant_id: str) -> MenuPerformanceResponse:
        top_items = [
            MenuPerformanceItem(menu_item_id="mock-item-1", name="Sample Item", quantity_sold=0, revenue=0.0),
        ]
        return MenuPerformanceResponse(restaurant_id=restaurant_id, top_items=top_items)
