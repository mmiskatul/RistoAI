from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

from app.core.enums import CouponDiscountType, CouponStatus, SubscriptionPlan, SubscriptionStatus
from app.schemas.common import BaseSchema


class SubscriptionOverviewQuery(BaseSchema):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
    search: str | None = None
    status: SubscriptionStatus | None = None
    billing_cycle: SubscriptionPlan | None = None
    months: int = Field(default=6, ge=1, le=12)


class SubscriptionSummaryResponse(BaseSchema):
    active_subscriptions: int
    trial_users: int
    monthly_revenue_mrr: float
    annual_revenue: float


class SubscriptionRevenuePointResponse(BaseSchema):
    label: str
    value: float


class SubscriptionSummaryCardResponse(BaseSchema):
    key: str
    label: str
    value: int | float
    value_formatted: str
    change_percent: float = 0.0
    change_label: str
    trend: str = "up"


class SubscriptionFilterChipResponse(BaseSchema):
    key: str
    label: str


class SubscriptionTableColumnResponse(BaseSchema):
    key: str
    label: str


class SubscriptionRowActionResponse(BaseSchema):
    key: str
    label: str
    method: str
    endpoint: str


class SubscriptionTableItemResponse(BaseSchema):
    user_id: str
    full_name: str
    email: EmailStr
    restaurant_name: str | None = None
    plan_name: str | None = None
    billing_cycle: SubscriptionPlan | None = None
    status: SubscriptionStatus | None = None
    start_date: datetime | None = None
    next_billing: datetime | None = None
    user_restaurant_label: str | None = None
    user_email_label: str | None = None
    billing_cycle_label: str | None = None
    status_label: str | None = None
    status_color: str | None = None
    start_date_formatted: str | None = None
    next_billing_formatted: str | None = None
    actions_menu: list[SubscriptionRowActionResponse] = Field(default_factory=list)


class SubscriptionOverviewResponse(BaseSchema):
    page_title: str = "Subscriptions Management"
    page_subtitle: str = "Manage restaurant subscriptions and track platform revenue."
    export_button_label: str = "Export Data"
    plan_button_label: str = "Our Subscriptions Plan"
    plan_button_endpoint: str = "/api/v1/subscriptions/plans/management"
    search_placeholder: str = "Search by name, restaurant or email..."
    filter_button_label: str = "Advanced Filters"
    filter_chips: list[SubscriptionFilterChipResponse] = Field(default_factory=list)
    summary_cards: list[SubscriptionSummaryCardResponse] = Field(default_factory=list)
    revenue_chart_title: str = "Monthly Subscription Revenue"
    revenue_chart_subtitle: str = "Revenue growth across all subscription tiers."
    revenue_chart_range_label: str = "Last 6 months"
    table_columns: list[SubscriptionTableColumnResponse] = Field(default_factory=list)
    pagination_label: str | None = None
    summary: SubscriptionSummaryResponse
    revenue_chart: list[SubscriptionRevenuePointResponse]
    total: int
    page: int
    page_size: int
    pages: int
    items: list[SubscriptionTableItemResponse]


class SubscriptionPlanResponse(BaseSchema):
    id: str
    name: str
    monthly_price: float
    annual_price: float
    trial_days: int
    features: list[str]
    is_visible: bool
    is_active: bool
    is_best_plan: bool
    created_at: str
    updated_at: str


class SubscriptionPlanUpdateRequest(BaseSchema):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    monthly_price: float | None = Field(default=None, ge=0)
    annual_price: float | None = Field(default=None, ge=0)
    trial_days: int | None = Field(default=None, ge=0, le=365)
    features: list[str] | None = None
    is_visible: bool | None = None
    is_active: bool | None = None
    is_best_plan: bool | None = None


class CouponQuery(BaseSchema):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
    search: str | None = None
    status: CouponStatus | None = None


class CouponResponse(BaseSchema):
    id: str
    code: str
    discount_type: CouponDiscountType
    value: float
    usage_limit: int
    usage_count: int
    expires_at: datetime | None = None
    status: CouponStatus
    created_at: str
    updated_at: str


class CouponCreateRequest(BaseSchema):
    code: str = Field(min_length=2, max_length=50)
    discount_type: CouponDiscountType
    value: float = Field(gt=0)
    usage_limit: int = Field(ge=1)
    expires_at: datetime | None = None
    status: CouponStatus = CouponStatus.ACTIVE


class CouponUpdateRequest(BaseSchema):
    discount_type: CouponDiscountType | None = None
    value: float | None = Field(default=None, gt=0)
    usage_limit: int | None = Field(default=None, ge=1)
    usage_count: int | None = Field(default=None, ge=0)
    expires_at: datetime | None = None
    status: CouponStatus | None = None


class CouponTableColumnResponse(BaseSchema):
    key: str
    label: str


class CouponFormFieldResponse(BaseSchema):
    key: str
    label: str
    input_type: str
    placeholder: str | None = None
    options: list[str] = Field(default_factory=list)


class CouponListResponse(BaseSchema):
    total: int
    page: int
    page_size: int
    pages: int
    items: list[CouponResponse]


class SubscriptionPlanManagementActionResponse(BaseSchema):
    key: str
    label: str
    method: str
    endpoint: str


class SubscriptionPlanDisplayResponse(BaseSchema):
    id: str
    badge_label: str = "Best Plan"
    name: str
    monthly_price: float
    monthly_price_formatted: str
    annual_price: float
    annual_price_formatted: str
    annual_savings_label: str | None = None
    trial_status_label: str
    features: list[str] = Field(default_factory=list)
    internal_actions_title: str = "Internal Actions"
    internal_actions: list[SubscriptionPlanManagementActionResponse] = Field(default_factory=list)
    visibility_label: str = "Plan Visibility"
    visibility_enabled: bool = True


class SubscriptionPlanManagementResponse(BaseSchema):
    page_title: str = "Subscriptions Plan Management"
    active_plan_section_title: str = "Active Subscription Plans"
    create_coupon_section_title: str = "Create Coupon"
    coupon_management_section_title: str = "Coupon Management"
    create_coupon_button_label: str = "Create Coupon Code"
    coupon_table_columns: list[CouponTableColumnResponse] = Field(default_factory=list)
    coupon_form_fields: list[CouponFormFieldResponse] = Field(default_factory=list)
    coupon_pagination_label: str | None = None
    plan: SubscriptionPlanResponse | None = None
    active_plan: SubscriptionPlanDisplayResponse | None = None
    plans: list[SubscriptionPlanResponse]
    coupons: CouponListResponse


class UserSubscriptionPlanResponse(BaseSchema):
    id: str
    name: str
    monthly_price: float
    annual_price: float
    trial_days: int
    features: list[str]
    is_best_plan: bool


class UserCurrentSubscriptionResponse(BaseSchema):
    selection_required: bool
    plan_name: str | None = None
    billing_cycle: SubscriptionPlan | None = None
    status: SubscriptionStatus | None = None
    started_at: datetime | None = None
    expires_at: datetime | None = None


class UserSubscriptionPlanListResponse(BaseSchema):
    selection_required: bool
    plans: list[UserSubscriptionPlanResponse]
    current_subscription: UserCurrentSubscriptionResponse


class UserSubscriptionSelectRequest(BaseSchema):
    billing_cycle: SubscriptionPlan
    start_trial: bool = True


class UserSubscriptionDiscountPreviewRequest(BaseSchema):
    billing_cycle: SubscriptionPlan
    coupon_code: str = Field(min_length=2, max_length=50)


class UserSubscriptionDiscountPreviewResponse(BaseSchema):
    coupon_code: str
    original_amount: float
    discount_amount: float
    final_amount: float


class SubscriptionActionResponse(BaseSchema):
    message: str


class SubscriptionPlanActionResponse(BaseSchema):
    message: str
    plan: SubscriptionPlanResponse


class CouponActionResponse(BaseSchema):
    message: str
    coupon: CouponResponse


class UserSubscriptionActionResponse(BaseSchema):
    message: str
    subscription: UserCurrentSubscriptionResponse
