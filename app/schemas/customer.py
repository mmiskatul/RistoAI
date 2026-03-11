from __future__ import annotations

from pydantic import EmailStr, Field

from app.schemas.common import BaseSchema


class CustomerCreate(BaseSchema):
    restaurant_id: str
    branch_id: str | None = None
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=500)


class CustomerUpdate(BaseSchema):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=500)
    branch_id: str | None = None


class CustomerRead(BaseSchema):
    id: str
    restaurant_id: str
    branch_id: str | None = None
    full_name: str
    email: EmailStr | None = None
    phone: str | None = None
    notes: str | None = None
    total_orders: int
    total_spent: float
    last_order_at: str | None = None
    created_at: str
    updated_at: str
