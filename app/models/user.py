from __future__ import annotations

from datetime import datetime

from app.core.enums import AccountStatus, AppLanguage, SubscriptionPlan, SubscriptionStatus, UserRole
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
    avatar_url: str | None = None
    profile_image_url: str | None = None
    restaurant_name: str | None = None
    restaurant_type: str | None = None
    location: str | None = None
    city_location: str | None = None
    number_of_seats: int | None = None
    average_spend_per_customer: float | None = None
    main_business_goal: str | None = None
    biggest_problem: str | None = None
    improvement_focus: str | None = None
    subscription_plan_name: str | None = None
    subscription_plan: SubscriptionPlan | None = None
    subscription_status: SubscriptionStatus | None = None
    account_status: AccountStatus | None = None
    subscription_started_at: datetime | None = None
    subscription_expires_at: datetime | None = None
