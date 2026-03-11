from __future__ import annotations

from app.schemas.common import BaseSchema


class DashboardSummary(BaseSchema):
    total_orders: int
    total_revenue: float
    active_menu_items: int
    total_customers: int
    average_order_value: float


class SalesAnalyticsResponse(BaseSchema):
    restaurant_id: str
    period: str
    total_sales: float
    total_orders: int
    average_order_value: float


class OrdersAnalyticsResponse(BaseSchema):
    restaurant_id: str
    by_status: dict[str, int]
    total_orders: int


class MenuPerformanceItem(BaseSchema):
    menu_item_id: str
    name: str
    quantity_sold: int
    revenue: float


class MenuPerformanceResponse(BaseSchema):
    restaurant_id: str
    top_items: list[MenuPerformanceItem]
