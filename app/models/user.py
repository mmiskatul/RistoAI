from __future__ import annotations

from datetime import datetime

from app.core.enums import AppLanguage, SubscriptionPlan, SubscriptionStatus, UserRole
from app.models.base import MongoDocument


class UserDocument(MongoDocument):
    email: str
    full_name: str
    phone: str | None = None
    hashed_password: str
    role: UserRole
    preferred_language: AppLanguage = AppLanguage.ENGLISH
    is_active: bool = True
    email_verified: bool = False
    restaurant_name: str | None = None
    location: str | None = None
    subscription_plan_name: str | None = None
    subscription_plan: SubscriptionPlan | None = None
    subscription_status: SubscriptionStatus | None = None
    subscription_started_at: datetime | None = None
    subscription_expires_at: datetime | None = None
