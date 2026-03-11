from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_customer_service
from app.schemas.common import PaginatedResponse
from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate
from app.services.customer import CustomerService

router = APIRouter()


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: CustomerCreate,
    current_user: dict = Depends(get_current_user),
    service: CustomerService = Depends(get_customer_service),
) -> CustomerRead:
    return await service.create_customer(current_user, payload)


@router.get("", response_model=PaginatedResponse[CustomerRead])
async def list_customers(
    restaurant_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: CustomerService = Depends(get_customer_service),
) -> PaginatedResponse[CustomerRead]:
    return await service.list_customers(current_user, restaurant_id, page, page_size)


@router.get("/{customer_id}", response_model=CustomerRead)
async def get_customer(
    customer_id: str,
    current_user: dict = Depends(get_current_user),
    service: CustomerService = Depends(get_customer_service),
) -> CustomerRead:
    return await service.get_customer(current_user, customer_id)


@router.patch("/{customer_id}", response_model=CustomerRead)
async def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    current_user: dict = Depends(get_current_user),
    service: CustomerService = Depends(get_customer_service),
) -> CustomerRead:
    return await service.update_customer(current_user, customer_id, payload)
