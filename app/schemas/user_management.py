from __future__ import annotations

from pydantic import EmailStr, Field

from app.core.enums import UserRole
from app.schemas.common import BaseSchema


class UserManagementQuery(BaseSchema):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
    search: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class UserManagementSummaryResponse(BaseSchema):
    total_users: int
    active_users: int
    suspended_users: int


class UserManagementListItemResponse(BaseSchema):
    id: str
    full_name: str
    email: EmailStr
    phone: str | None = None
    role: UserRole
    restaurant_name: str | None = None
    location: str | None = None
    plan: str | None = None
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


class UserManagementActionResponse(BaseSchema):
    message: str
    user: UserManagementListItemResponse
