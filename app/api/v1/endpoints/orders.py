from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_order_service
from app.schemas.common import PaginatedResponse
from app.schemas.order import OrderCreate, OrderRead, OrderStatusUpdate
from app.services.order import OrderService

router = APIRouter()


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate,
    current_user: dict = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderRead:
    return await service.create_order(current_user, payload)


@router.get("", response_model=PaginatedResponse[OrderRead])
async def list_orders(
    restaurant_id: str,
    branch_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> PaginatedResponse[OrderRead]:
    return await service.list_orders(current_user, restaurant_id, page, page_size, branch_id)


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: str,
    current_user: dict = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderRead:
    return await service.get_order(current_user, order_id)


@router.patch("/{order_id}/status", response_model=OrderRead)
async def update_order_status(
    order_id: str,
    payload: OrderStatusUpdate,
    current_user: dict = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderRead:
    return await service.update_order_status(current_user, order_id, payload)


@router.post("/{order_id}/cancel", response_model=OrderRead)
async def cancel_order(
    order_id: str,
    current_user: dict = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderRead:
    return await service.cancel_order(current_user, order_id)
