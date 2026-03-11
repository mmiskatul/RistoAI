from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_menu_service
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.menu import MenuAvailabilityUpdate, MenuItemCreate, MenuItemRead, MenuItemUpdate
from app.services.menu import MenuService

router = APIRouter()


@router.post("", response_model=MenuItemRead, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: MenuItemCreate,
    current_user: dict = Depends(get_current_user),
    service: MenuService = Depends(get_menu_service),
) -> MenuItemRead:
    return await service.create_item(current_user, payload)


@router.get("", response_model=PaginatedResponse[MenuItemRead])
async def list_items(
    restaurant_id: str,
    branch_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: MenuService = Depends(get_menu_service),
) -> PaginatedResponse[MenuItemRead]:
    return await service.list_items(current_user, restaurant_id, page, page_size, branch_id)


@router.get("/{item_id}", response_model=MenuItemRead)
async def get_item(
    item_id: str,
    current_user: dict = Depends(get_current_user),
    service: MenuService = Depends(get_menu_service),
) -> MenuItemRead:
    return await service.get_item(current_user, item_id)


@router.patch("/{item_id}", response_model=MenuItemRead)
async def update_item(
    item_id: str,
    payload: MenuItemUpdate,
    current_user: dict = Depends(get_current_user),
    service: MenuService = Depends(get_menu_service),
) -> MenuItemRead:
    return await service.update_item(current_user, item_id, payload)


@router.delete("/{item_id}", response_model=MessageResponse)
async def delete_item(
    item_id: str,
    current_user: dict = Depends(get_current_user),
    service: MenuService = Depends(get_menu_service),
) -> MessageResponse:
    return await service.delete_item(current_user, item_id)


@router.patch("/{item_id}/availability", response_model=MenuItemRead)
async def toggle_availability(
    item_id: str,
    payload: MenuAvailabilityUpdate,
    current_user: dict = Depends(get_current_user),
    service: MenuService = Depends(get_menu_service),
) -> MenuItemRead:
    return await service.toggle_availability(current_user, item_id, payload)
