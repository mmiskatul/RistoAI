from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    RESTAURANT_OWNER = "restaurant_owner"
    MANAGER = "manager"
    STAFF = "staff"


class SubscriptionPlan(StrEnum):
    ONE_MONTH = "1_month"
    ONE_YEAR = "1_year"


class SubscriptionStatus(StrEnum):
    ACTIVE = "active"
    TRIAL = "trial"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
