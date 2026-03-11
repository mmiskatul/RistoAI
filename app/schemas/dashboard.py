from __future__ import annotations

from pydantic import Field

from app.schemas.common import BaseSchema


class DashboardKpiResponse(BaseSchema):
    total_users: int
    active_users: int
    verified_users: int
    completed_onboarding: int
    pending_verifications: int
    admins: int
    restaurant_owners: int
    managers: int
    staff: int


class DashboardMonthlyPointResponse(BaseSchema):
    month: int = Field(ge=1, le=12)
    label: str
    value: int = Field(ge=0)


class DashboardRoleBreakdownResponse(BaseSchema):
    role: str
    label: str
    value: int = Field(ge=0)


class DashboardChartsResponse(BaseSchema):
    monthly_new_users: list[DashboardMonthlyPointResponse]
    monthly_completed_onboarding: list[DashboardMonthlyPointResponse]
    users_by_role: list[DashboardRoleBreakdownResponse]


class DashboardMetaResponse(BaseSchema):
    year: int


class DashboardOverviewResponse(BaseSchema):
    summary: DashboardKpiResponse
    charts: DashboardChartsResponse
    meta: DashboardMetaResponse


class DashboardUserMetricsResponse(BaseSchema):
    total_users: int
    active_users: int
    verified_users: int
    admins: int
    restaurant_owners: int
    managers: int
    staff: int
