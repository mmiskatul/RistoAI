from __future__ import annotations

from pydantic import EmailStr, Field

from app.core.enums import UserRole
from app.schemas.auth import AuthUserResponse
from app.schemas.common import BaseSchema


class StaffCreate(BaseSchema):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    phone: str | None = Field(default=None, max_length=30)
    role: UserRole
    restaurant_ids: list[str] = Field(min_length=1)
    branch_ids: list[str] = Field(default_factory=list)


class StaffUpdate(BaseSchema):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    is_active: bool | None = None
    restaurant_ids: list[str] | None = None
    branch_ids: list[str] | None = None


class StaffRead(AuthUserResponse):
    pass
