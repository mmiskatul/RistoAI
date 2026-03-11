from __future__ import annotations

from pydantic import Field

from app.core.enums import NotificationType
from app.models.base import MongoDocument
from app.utils.object_id import PyObjectId


class NotificationDocument(MongoDocument):
    user_id: PyObjectId
    restaurant_id: PyObjectId | None = None
    title: str
    message: str
    type: NotificationType = NotificationType.SYSTEM
    is_read: bool = False
    metadata: dict = Field(default_factory=dict)
    read_at: str | None = None
