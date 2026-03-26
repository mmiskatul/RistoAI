from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.core.enums import UserRole
from app.dependencies.auth import require_roles
from app.dependencies.services import get_user_management_service
from app.schemas.user_management import (
    UserManagementActionResponse,
    UserManagementListResponse,
    UserManagementQuery,
    UserManagementUpdateRequest,
)
from app.services.user_management import UserManagementService

router = APIRouter()


@router.get('/management', response_model=UserManagementListResponse, summary='Admin Users Management', description='Returns the full admin users management page payload including search, filters, summary cards, table rows, and action menu endpoints.')
async def get_users_management_page(
    query: UserManagementQuery = Depends(),
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: UserManagementService = Depends(get_user_management_service),
) -> UserManagementListResponse:
    return await service.get_management_page(query)


@router.patch('/{user_id}', response_model=UserManagementActionResponse, summary='Update User', description='Updates an admin-managed user row.')
async def update_user(
    user_id: str,
    payload: UserManagementUpdateRequest,
    current_user: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: UserManagementService = Depends(get_user_management_service),
) -> UserManagementActionResponse:
    return await service.update_user(actor_user=current_user, user_id=user_id, payload=payload)


@router.post('/{user_id}/suspend', response_model=UserManagementActionResponse, summary='Suspend User', description='Suspends a user account from the admin users management page.')
async def suspend_user(
    user_id: str,
    current_user: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: UserManagementService = Depends(get_user_management_service),
) -> UserManagementActionResponse:
    return await service.suspend_user(actor_user=current_user, user_id=user_id)


@router.post('/{user_id}/activate', response_model=UserManagementActionResponse, summary='Activate User', description='Reactivates a suspended user account from the admin users management page.')
async def activate_user(
    user_id: str,
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: UserManagementService = Depends(get_user_management_service),
) -> UserManagementActionResponse:
    return await service.activate_user(user_id)


@router.delete('/{user_id}', status_code=status.HTTP_204_NO_CONTENT, summary='Delete User', description='Deletes a user account from the admin users management page.')
async def delete_user(
    user_id: str,
    current_user: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: UserManagementService = Depends(get_user_management_service),
) -> Response:
    await service.delete_user(actor_user=current_user, user_id=user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
