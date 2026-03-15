from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.enums import UserRole
from app.dependencies.auth import require_roles
from app.dependencies.services import get_support_service
from app.schemas.support import (
    SupportTicketActionResponse,
    SupportTicketCreateRequest,
    SupportTicketDetailResponse,
    SupportTicketManagementResponse,
    UserSupportTicketListResponse,
    SupportTicketQuery,
    SupportTicketReplyRequest,
)
from app.services.support import SupportService

router = APIRouter()


@router.post('/tickets', response_model=SupportTicketActionResponse, tags=['Restaurant Support'])
async def create_support_ticket(
    payload: SupportTicketCreateRequest,
    current_user: dict = Depends(require_roles(UserRole.RESTAURANT_OWNER, UserRole.MANAGER, UserRole.STAFF)),
    service: SupportService = Depends(get_support_service),
) -> SupportTicketActionResponse:
    return await service.create_ticket(current_user, payload)


@router.get('/user/tickets', response_model=UserSupportTicketListResponse, tags=['Restaurant Support'])
async def get_user_support_tickets(
    query: SupportTicketQuery = Depends(),
    current_user: dict = Depends(require_roles(UserRole.RESTAURANT_OWNER, UserRole.MANAGER, UserRole.STAFF)),
    service: SupportService = Depends(get_support_service),
) -> UserSupportTicketListResponse:
    return await service.get_user_tickets(current_user, query)


@router.get('/user/tickets/{ticket_id}', response_model=SupportTicketDetailResponse, tags=['Restaurant Support'])
async def get_user_support_ticket_detail(
    ticket_id: str,
    current_user: dict = Depends(require_roles(UserRole.RESTAURANT_OWNER, UserRole.MANAGER, UserRole.STAFF)),
    service: SupportService = Depends(get_support_service),
) -> SupportTicketDetailResponse:
    return await service.get_user_ticket_detail(current_user, ticket_id)


@router.get('/management', response_model=SupportTicketManagementResponse, tags=['Support Management'])
async def get_support_management(
    query: SupportTicketQuery = Depends(),
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: SupportService = Depends(get_support_service),
) -> SupportTicketManagementResponse:
    return await service.get_management_page(query)


@router.get('/tickets/{ticket_id}', response_model=SupportTicketDetailResponse, tags=['Support Management'])
async def get_support_ticket_detail(
    ticket_id: str,
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: SupportService = Depends(get_support_service),
) -> SupportTicketDetailResponse:
    return await service.get_ticket_detail(ticket_id)


@router.post('/tickets/{ticket_id}/reply', response_model=SupportTicketActionResponse, tags=['Support Management'])
async def reply_support_ticket(
    ticket_id: str,
    payload: SupportTicketReplyRequest,
    current_user: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: SupportService = Depends(get_support_service),
) -> SupportTicketActionResponse:
    return await service.reply_to_ticket(ticket_id, current_user, payload)


@router.post('/tickets/{ticket_id}/resolve', response_model=SupportTicketActionResponse, tags=['Support Management'])
async def resolve_support_ticket(
    ticket_id: str,
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: SupportService = Depends(get_support_service),
) -> SupportTicketActionResponse:
    return await service.resolve_ticket(ticket_id)
