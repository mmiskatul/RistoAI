from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.enums import SupportTicketPriority, SupportTicketStatus
from app.models.base import MongoDocument
from app.utils.object_id import PyObjectId


class SupportTicketDocument(MongoDocument):
    ticket_number: str
    user_id: PyObjectId
    user_name: str
    email: str
    phone: str | None = None
    restaurant_name: str | None = None
    location: str | None = None
    subject: str
    status: SupportTicketStatus = SupportTicketStatus.OPEN
    priority: SupportTicketPriority = SupportTicketPriority.NORMAL
    messages: list[dict[str, Any]]
    resolved_at: datetime | None = None
