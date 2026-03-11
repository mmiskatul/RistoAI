from __future__ import annotations

from datetime import datetime

from app.models.base import MongoDocument
from app.utils.object_id import PyObjectId


class AuthCodeDocument(MongoDocument):
    user_id: PyObjectId
    email: str
    purpose: str
    code_hash: str
    expires_at: datetime
    consumed_at: datetime | None = None
