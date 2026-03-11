from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.core.enums import UserRole
from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.services import get_restaurant_service
from app.schemas.common import PaginatedResponse
from app.schemas.restaurant import RestaurantCreate, RestaurantRead, RestaurantUpdate
from app.services.restaurant import RestaurantService

router = APIRouter()


@router.post("", response_model=RestaurantRead, status_code=status.HTTP_201_CREATED)
async def create_restaurant(
    payload: RestaurantCreate,
    current_user: dict = Depends(require_roles(UserRole.RESTAURANT_OWNER, UserRole.SUPER_ADMIN)),
    service: RestaurantService = Depends(get_restaurant_service),
) -> RestaurantRead:
    return await service.create_restaurant(current_user, payload)


@router.get("", response_model=PaginatedResponse[RestaurantRead])
async def list_restaurants(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: RestaurantService = Depends(get_restaurant_service),
) -> PaginatedResponse[RestaurantRead]:
    return await service.list_restaurants(current_user, page, page_size)


@router.get("/{restaurant_id}", response_model=RestaurantRead)
async def get_restaurant(
    restaurant_id: str,
    current_user: dict = Depends(get_current_user),
    service: RestaurantService = Depends(get_restaurant_service),
) -> RestaurantRead:
    return await service.get_restaurant(current_user, restaurant_id)


@router.patch("/{restaurant_id}", response_model=RestaurantRead)
async def update_restaurant(
    restaurant_id: str,
    payload: RestaurantUpdate,
    current_user: dict = Depends(get_current_user),
    service: RestaurantService = Depends(get_restaurant_service),
) -> RestaurantRead:
    return await service.update_restaurant(current_user, restaurant_id, payload)
