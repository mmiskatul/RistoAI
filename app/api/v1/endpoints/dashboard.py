from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_analytics_service
from app.schemas.analytics import DashboardSummary
from app.services.analytics import AnalyticsService

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    restaurant_id: str,
    current_user: dict = Depends(get_current_user),
    service: AnalyticsService = Depends(get_analytics_service),
) -> DashboardSummary:
    return await service.dashboard_summary(current_user, restaurant_id)
