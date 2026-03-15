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
    amount: float
    started_at: datetime
    expires_at: datetime | None = None
