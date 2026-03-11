from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.core.enums import UserRole
from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.services import get_staff_service
from app.schemas.common import PaginatedResponse
from app.schemas.staff import StaffCreate, StaffRead, StaffUpdate
from app.services.staff import StaffService

router = APIRouter()


@router.post("", response_model=StaffRead, status_code=status.HTTP_201_CREATED)
async def create_staff(
    payload: StaffCreate,
    current_user: dict = Depends(require_roles(UserRole.RESTAURANT_OWNER, UserRole.MANAGER, UserRole.SUPER_ADMIN)),
    service: StaffService = Depends(get_staff_service),
) -> StaffRead:
    return await service.create_staff(current_user, payload)


@router.get("", response_model=PaginatedResponse[StaffRead])
async def list_staff(
    restaurant_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: StaffService = Depends(get_staff_service),
) -> PaginatedResponse[StaffRead]:
    return await service.list_staff(current_user, restaurant_id, page, page_size)


@router.patch("/{staff_id}", response_model=StaffRead)
async def update_staff(
    staff_id: str,
    payload: StaffUpdate,
    current_user: dict = Depends(get_current_user),
    service: StaffService = Depends(get_staff_service),
) -> StaffRead:
    return await service.update_staff(current_user, staff_id, payload)
