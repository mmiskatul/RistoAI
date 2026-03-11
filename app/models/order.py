from __future__ import annotations

from pydantic import Field

from app.core.enums import OrderStatus, PaymentStatus
from app.models.base import MongoDocument
from app.utils.object_id import PyObjectId


class OrderItemEmbedded(MongoDocument):
    menu_item_id: PyObjectId
    name: str
    quantity: int
    unit_price: float
    line_total: float
    notes: str | None = None


class OrderDocument(MongoDocument):
    restaurant_id: PyObjectId
    branch_id: PyObjectId
    customer_id: PyObjectId | None = None
    items: list[dict] = Field(default_factory=list)
    subtotal: float
    tax: float
    discount: float
    total: float
    payment_status: PaymentStatus = PaymentStatus.PENDING
    order_status: OrderStatus = OrderStatus.PENDING
