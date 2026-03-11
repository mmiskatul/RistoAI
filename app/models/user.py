from __future__ import annotations

from app.core.enums import UserRole
from app.models.base import MongoDocument


class UserDocument(MongoDocument):
    email: str
    full_name: str
    phone: str | None = None
    hashed_password: str
    role: UserRole
    is_active: bool = True
    email_verified: bool = False
