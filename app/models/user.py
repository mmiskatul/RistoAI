from __future__ import annotations

from pydantic import Field

from app.core.enums import UserRole
from app.models.base import MongoDocument
from app.utils.object_id import PyObjectId


class UserDocument(MongoDocument):
    email: str
    full_name: str
    phone: str | None = None
    hashed_password: str
    role: UserRole
    is_active: bool = True
    email_verified: bool = False
    restaurant_ids: list[PyObjectId] = Field(default_factory=list)
    branch_ids: list[PyObjectId] = Field(default_factory=list)
