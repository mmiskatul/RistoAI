from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    RESTAURANT_OWNER = "restaurant_owner"
    MANAGER = "manager"
    STAFF = "staff"
