from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query

from app.core.enums import UserRole
from app.dependencies.auth import require_roles
from app.dependencies.services import get_dashboard_service
from app.schemas.dashboard import DashboardOverviewResponse, DashboardUserMetricsResponse
from app.services.dashboard import DashboardService

router = APIRouter()


@router.get('/overview', response_model=DashboardOverviewResponse)
async def get_dashboard_overview(
    year: int = Query(default_factory=lambda: datetime.now(UTC).year, ge=2000, le=2100),
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardOverviewResponse:
    return await service.get_overview(year)


@router.get('/users/metrics', response_model=DashboardUserMetricsResponse)
async def get_user_metrics(
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardUserMetricsResponse:
    return await service.get_user_metrics()
