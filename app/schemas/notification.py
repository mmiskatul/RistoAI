from __future__ import annotations

from app.core.enums import NotificationType
from app.schemas.common import BaseSchema


class NotificationRead(BaseSchema):
    id: str
    user_id: str
    restaurant_id: str | None = None
    title: str
    message: str
    type: NotificationType
    is_read: bool
    metadata: dict
    read_at: str | None = None
    created_at: str
    updated_at: str


class NotificationMarkRead(BaseSchema):
    is_read: bool = True
