from __future__ import annotations

from pydantic import Field, field_validator

from app.core.enums import OrderStatus, PaymentStatus
from app.schemas.common import BaseSchema


class OrderItemCreate(BaseSchema):
    menu_item_id: str
    quantity: int = Field(ge=1, le=100)
    notes: str | None = Field(default=None, max_length=250)


class OrderCreate(BaseSchema):
    restaurant_id: str
    branch_id: str
    customer_id: str | None = None
    items: list[OrderItemCreate] = Field(min_length=1)
    discount: float = Field(default=0, ge=0)
    payment_status: PaymentStatus = PaymentStatus.PENDING

    @field_validator("items")
    @classmethod
    def ensure_items_present(cls, value: list[OrderItemCreate]) -> list[OrderItemCreate]:
        if not value:
            raise ValueError("At least one order item is required")
        return value


class OrderStatusUpdate(BaseSchema):
    order_status: OrderStatus


class OrderReadItem(BaseSchema):
    menu_item_id: str
    name: str
    quantity: int
    unit_price: float
    line_total: float
    notes: str | None = None


class OrderRead(BaseSchema):
    id: str
    restaurant_id: str
    branch_id: str
    customer_id: str | None = None
    items: list[OrderReadItem]
    subtotal: float
    tax: float
    discount: float
    total: float
    payment_status: PaymentStatus
    order_status: OrderStatus
    created_at: str
    updated_at: str
