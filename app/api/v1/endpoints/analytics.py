from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_analytics_service
from app.schemas.analytics import MenuPerformanceResponse, OrdersAnalyticsResponse, SalesAnalyticsResponse
from app.services.analytics import AnalyticsService

router = APIRouter()


@router.get("/sales", response_model=SalesAnalyticsResponse)
async def sales_analytics(
    restaurant_id: str,
    current_user: dict = Depends(get_current_user),
    service: AnalyticsService = Depends(get_analytics_service),
) -> SalesAnalyticsResponse:
    return await service.sales_analytics(current_user, restaurant_id)


@router.get("/orders", response_model=OrdersAnalyticsResponse)
async def orders_analytics(
    restaurant_id: str,
    current_user: dict = Depends(get_current_user),
    service: AnalyticsService = Depends(get_analytics_service),
) -> OrdersAnalyticsResponse:
    return await service.orders_analytics(current_user, restaurant_id)


@router.get("/menu-performance", response_model=MenuPerformanceResponse)
async def menu_performance(
    restaurant_id: str,
    current_user: dict = Depends(get_current_user),
    service: AnalyticsService = Depends(get_analytics_service),
) -> MenuPerformanceResponse:
    return await service.menu_performance(current_user, restaurant_id)
