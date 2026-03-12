from __future__ import annotations

from datetime import datetime

from app.models.base import MongoDocument


class SubscriptionPlanDocument(MongoDocument):
    name: str
    monthly_price: float
    annual_price: float
    trial_days: int
    features: list[str]
    is_visible: bool = True
    is_active: bool = True
    is_best_plan: bool = False
