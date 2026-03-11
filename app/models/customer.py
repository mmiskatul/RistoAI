from __future__ import annotations

from app.models.base import MongoDocument
from app.utils.object_id import PyObjectId


class CustomerDocument(MongoDocument):
    restaurant_id: PyObjectId
    branch_id: PyObjectId | None = None
    full_name: str
    email: str | None = None
    phone: str | None = None
    notes: str | None = None
    total_orders: int = 0
    total_spent: float = 0.0
    last_order_at: str | None = None
