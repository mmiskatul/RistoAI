from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_branch_service
from app.schemas.branch import BranchCreate, BranchRead, BranchUpdate
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services.branch import BranchService

router = APIRouter()


@router.post("", response_model=BranchRead, status_code=status.HTTP_201_CREATED)
async def create_branch(
    payload: BranchCreate,
    current_user: dict = Depends(get_current_user),
    service: BranchService = Depends(get_branch_service),
) -> BranchRead:
    return await service.create_branch(current_user, payload)


@router.get("", response_model=PaginatedResponse[BranchRead])
async def list_branches(
    restaurant_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: BranchService = Depends(get_branch_service),
) -> PaginatedResponse[BranchRead]:
    return await service.list_branches(current_user, restaurant_id, page, page_size)


@router.patch("/{branch_id}", response_model=BranchRead)
async def update_branch(
    branch_id: str,
    payload: BranchUpdate,
    current_user: dict = Depends(get_current_user),
    service: BranchService = Depends(get_branch_service),
) -> BranchRead:
    return await service.update_branch(current_user, branch_id, payload)


@router.delete("/{branch_id}", response_model=MessageResponse)
async def delete_branch(
    branch_id: str,
    current_user: dict = Depends(get_current_user),
    service: BranchService = Depends(get_branch_service),
) -> MessageResponse:
    return await service.delete_branch(current_user, branch_id)
