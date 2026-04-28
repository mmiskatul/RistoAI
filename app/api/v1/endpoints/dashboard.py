from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query

from app.core.enums import UserRole
from app.dependencies.auth import require_roles
from app.dependencies.services import get_dashboard_service
from app.schemas.dashboard import DashboardAnalyticsResponse, DashboardOverviewResponse, DashboardUserMetricsResponse
from app.services.dashboard import DashboardService

router = APIRouter()


@router.get('/overview', response_model=DashboardOverviewResponse, tags=['Admin Dashboard'], summary='Admin Dashboard Overview', description='Returns the admin dashboard page payload including sidebar, header, KPI cards, revenue growth, and user growth sections.')
async def get_dashboard_overview(
    year: int = Query(default_factory=lambda: datetime.now(UTC).year, ge=2000, le=2100),
    current_user: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardOverviewResponse:
    return await service.get_overview(current_user, year)


@router.get('/users/metrics', response_model=DashboardUserMetricsResponse, tags=['Admin Dashboard'], summary='Admin Dashboard User Metrics', description='Returns the compact user metrics block used by the admin dashboard.')
async def get_user_metrics(
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardUserMetricsResponse:
    return await service.get_user_metrics()


@router.get('/analytics', response_model=DashboardAnalyticsResponse, tags=['Admin Dashboard'], summary='Admin Dashboard Analytics', description='Returns the platform analytics payload for the admin analytics page.')
async def get_dashboard_analytics(
    range_key: str = Query(default="30d", pattern="^(7d|30d|90d)$"),
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardAnalyticsResponse:
    return await service.get_analytics(range_key=range_key)
