from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

from app.core.enums import SubscriptionPlan, SubscriptionStatus, UserRole
from app.schemas.common import BaseSchema


class UserManagementQuery(BaseSchema):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
    search: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    subscription_status: SubscriptionStatus | None = None


class UserManagementSummaryResponse(BaseSchema):
    total_users: int
    active_users: int
    suspended_users: int
    trial_users: int


class UserManagementSummaryCardResponse(BaseSchema):
    key: str
    label: str
    value: int
    value_formatted: str
    change_percent: float = 0.0
    change_label: str
    trend: str = "up"


class UserManagementFilterChipResponse(BaseSchema):
    key: str
    label: str


class UserManagementTableColumnResponse(BaseSchema):
    key: str
    label: str


class UserManagementRowActionResponse(BaseSchema):
    key: str
    label: str
    method: str
    endpoint: str


class UserManagementListItemResponse(BaseSchema):
    id: str
    full_name: str
    email: EmailStr
    phone: str | None = None
    role: UserRole
    restaurant_name: str | None = None
    location: str | None = None
    subscription_plan_name: str | None = None
    subscription_plan: SubscriptionPlan | None = None
    subscription_status: SubscriptionStatus | None = None
    subscription_started_at: datetime | None = None
    subscription_expires_at: datetime | None = None
    status: str
    is_active: bool
    email_verified: bool
    join_date: str
    created_at: str
    updated_at: str


class UserManagementListResponse(BaseSchema):
    summary: UserManagementSummaryResponse
    total: int
    page: int
    page_size: int
    pages: int
    items: list[UserManagementListItemResponse]


class UserManagementUpdateRequest(BaseSchema):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    role: UserRole | None = None
    is_active: bool | None = None
    email_verified: bool | None = None
    restaurant_name: str | None = Field(default=None, min_length=2, max_length=120)
    location: str | None = Field(default=None, min_length=2, max_length=120)
    subscription_plan_name: str | None = Field(default=None, min_length=2, max_length=120)
    subscription_plan: SubscriptionPlan | None = None
    subscription_status: SubscriptionStatus | None = None
    subscription_started_at: datetime | None = None
    subscription_expires_at: datetime | None = None


class UserManagementActionResponse(BaseSchema):
    message: str
    user: UserManagementListItemResponse
