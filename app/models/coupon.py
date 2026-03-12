from __future__ import annotations

from datetime import datetime

from app.core.enums import CouponDiscountType, CouponStatus
from app.models.base import MongoDocument


class CouponDocument(MongoDocument):
    code: str
    discount_type: CouponDiscountType
    value: float
    usage_limit: int
    usage_count: int = 0
    expires_at: datetime | None = None
    status: CouponStatus = CouponStatus.ACTIVE
