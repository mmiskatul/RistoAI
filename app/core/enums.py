from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    RESTAURANT_OWNER = "restaurant_owner"
    MANAGER = "manager"
    STAFF = "staff"


class OrderStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    READY = "ready"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class NotificationType(StrEnum):
    SYSTEM = "system"
    ORDER = "order"
    ANALYTICS = "analytics"
    AI_INSIGHT = "ai_insight"


class InsightType(StrEnum):
    RECOMMENDATIONS = "recommendations"
    DEMAND_FORECAST = "demand_forecast"
    WASTE_REDUCTION = "waste_reduction"
    MENU_OPTIMIZATION = "menu_optimization"
