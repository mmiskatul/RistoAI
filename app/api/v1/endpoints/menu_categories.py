from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_menu_service
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.menu import MenuCategoryCreate, MenuCategoryRead, MenuCategoryUpdate
from app.services.menu import MenuService

router = APIRouter()


@router.post("", response_model=MenuCategoryRead, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: MenuCategoryCreate,
    current_user: dict = Depends(get_current_user),
    service: MenuService = Depends(get_menu_service),
) -> MenuCategoryRead:
    return await service.create_category(current_user, payload)


@router.get("", response_model=PaginatedResponse[MenuCategoryRead])
async def list_categories(
    restaurant_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: MenuService = Depends(get_menu_service),
) -> PaginatedResponse[MenuCategoryRead]:
    return await service.list_categories(current_user, restaurant_id, page, page_size)


@router.patch("/{category_id}", response_model=MenuCategoryRead)
async def update_category(
    category_id: str,
    payload: MenuCategoryUpdate,
    current_user: dict = Depends(get_current_user),
    service: MenuService = Depends(get_menu_service),
) -> MenuCategoryRead:
    return await service.update_category(current_user, category_id, payload)


@router.delete("/{category_id}", response_model=MessageResponse)
async def delete_category(
    category_id: str,
    current_user: dict = Depends(get_current_user),
    service: MenuService = Depends(get_menu_service),
) -> MessageResponse:
    return await service.delete_category(current_user, category_id)
