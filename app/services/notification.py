from __future__ import annotations

from app.core.exceptions import AuthorizationException
from app.repositories.notification import NotificationRepository
from app.schemas.common import PaginatedResponse
from app.schemas.notification import NotificationRead
from app.services.base import BaseService
from app.utils.datetime import utc_now
from app.utils.pagination import build_pagination_meta


class NotificationService(BaseService):
    def __init__(self, notification_repository: NotificationRepository) -> None:
        self.notification_repository = notification_repository

    async def list_notifications(self, current_user: dict, page: int, page_size: int) -> PaginatedResponse[NotificationRead]:
        notifications, total = await self.notification_repository.list_for_user(str(current_user["_id"]), page, page_size)
        items = [NotificationRead(**document) for document in self.serialize_list(notifications)]
        return PaginatedResponse[NotificationRead](**build_pagination_meta(total=total, page=page, page_size=page_size), items=items)

    async def mark_read(self, current_user: dict, notification_id: str) -> NotificationRead:
        notification = await self.notification_repository.get_by_id(notification_id)
        if str(notification["user_id"]) != str(current_user["_id"]):
            raise AuthorizationException("You do not have access to this notification")
        notification = await self.notification_repository.update(
            notification_id,
            {"is_read": True, "read_at": utc_now().isoformat()},
        )
        return NotificationRead(**self.serialize(notification))
