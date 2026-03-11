from __future__ import annotations

from pydantic import Field

from app.schemas.common import BaseSchema


class BranchCreate(BaseSchema):
    restaurant_id: str
    name: str = Field(min_length=2, max_length=150)
    address: str = Field(min_length=5, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    manager_ids: list[str] = Field(default_factory=list)


class BranchUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    address: str | None = Field(default=None, min_length=5, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    manager_ids: list[str] | None = None
    is_active: bool | None = None


class BranchRead(BaseSchema):
    id: str
    restaurant_id: str
    name: str
    address: str
    phone: str | None = None
    manager_ids: list[str]
    is_active: bool
    created_at: str
    updated_at: str
