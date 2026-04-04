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
    value: int | float = Field(ge=0)


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


class DashboardSidebarItemResponse(BaseSchema):
    key: str
    label: str
    icon_key: str
    endpoint: str
    active: bool = False


class DashboardSidebarFooterActionResponse(BaseSchema):
    label: str
    icon_key: str
    endpoint: str


class DashboardHeaderActionResponse(BaseSchema):
    key: str
    label: str


class DashboardHeaderProfileResponse(BaseSchema):
    full_name: str
    avatar_url: str | None = None


class DashboardHeaderResponse(BaseSchema):
    title: str
    subtitle: str
    notification_count: int = 0
    actions: list[DashboardHeaderActionResponse] = Field(default_factory=list)
    profile: DashboardHeaderProfileResponse


class DashboardTopCardResponse(BaseSchema):
    key: str
    label: str
    value: int | float
    value_formatted: str
    change_percent: float = 0.0
    change_label: str
    trend: str = "up"
    icon_key: str


class DashboardRevenueGrowthResponse(BaseSchema):
    title: str = "Revenue Growth"
    period_options: list[str] = Field(default_factory=lambda: ["Weekly", "Monthly"])
    active_period: str = "Monthly"
    selected_year: int
    year_options: list[int] = Field(default_factory=list)
    points: list[DashboardMonthlyPointResponse] = Field(default_factory=list)
    y_axis_label: str = "Revenue"


class DashboardUserGrowthSliceResponse(BaseSchema):
    label: str
    value: int = Field(ge=0)
    percentage: float = Field(ge=0)
    color_key: str


class DashboardUserGrowthResponse(BaseSchema):
    title: str = "User Growth"
    total_label: str = "Total"
    total_value: int = Field(ge=0)
    total_value_formatted: str
    center_value_label: str = "TOTAL"
    slices: list[DashboardUserGrowthSliceResponse] = Field(default_factory=list)


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
