from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_notification_service
from app.schemas.common import PaginatedResponse
from app.schemas.notification import NotificationRead
from app.services.notification import NotificationService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[NotificationRead])
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> PaginatedResponse[NotificationRead]:
    return await service.list_notifications(current_user, page, page_size)


@router.patch("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_as_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationRead:
    return await service.mark_read(current_user, notification_id)
