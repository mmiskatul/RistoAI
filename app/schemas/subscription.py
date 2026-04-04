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


class SubscriptionOverviewResponse(BaseSchema):
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
    name: str
    monthly_price: float
    annual_price: float
    features: list[str] = Field(default_factory=list)
    visibility_enabled: bool = True


class SubscriptionPlanManagementResponse(BaseSchema):
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


class UserSubscriptionCheckoutSessionResponse(BaseSchema):
    session_id: str
    checkout_url: str
    publishable_key: str | None = None


class UserSubscriptionPortalResponse(BaseSchema):
    portal_url: str


class StripeWebhookResponse(BaseSchema):
    received: bool = True
    event_type: str


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
