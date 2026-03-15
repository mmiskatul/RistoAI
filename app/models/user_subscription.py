from __future__ import annotations

from datetime import datetime

from app.core.enums import SubscriptionPlan, SubscriptionStatus
from app.models.base import MongoDocument
from app.utils.object_id import PyObjectId


class UserSubscriptionDocument(MongoDocument):
    user_id: PyObjectId
    subscription_plan_id: PyObjectId
    plan_name: str
    billing_cycle: SubscriptionPlan
    status: SubscriptionStatus
    start_trial: bool
    trial_days: int
    original_amount: float
    discount_amount: float = 0.0
    amount: float
    coupon_id: PyObjectId | None = None
    coupon_code: str | None = None
    started_at: datetime
    expires_at: datetime | None = None
