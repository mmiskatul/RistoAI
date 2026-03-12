from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.core.enums import UserRole
from app.dependencies.auth import require_roles
from app.dependencies.services import get_subscription_service
from app.schemas.subscription import (
    CouponActionResponse,
    CouponCreateRequest,
    CouponQuery,
    CouponUpdateRequest,
    SubscriptionActionResponse,
    SubscriptionOverviewQuery,
    SubscriptionOverviewResponse,
    SubscriptionPlanActionResponse,
    SubscriptionPlanCreateRequest,
    SubscriptionPlanManagementResponse,
    SubscriptionPlanUpdateRequest,
)
from app.services.subscription import SubscriptionService

router = APIRouter()


@router.get('/overview', response_model=SubscriptionOverviewResponse)
async def get_subscription_overview(
    query: SubscriptionOverviewQuery = Depends(),
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> SubscriptionOverviewResponse:
    return await service.get_overview(query)


@router.get('/plans/management', response_model=SubscriptionPlanManagementResponse)
async def get_subscription_plan_management(
    query: CouponQuery = Depends(),
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> SubscriptionPlanManagementResponse:
    return await service.get_plan_management(query)


@router.post('/plans', response_model=SubscriptionPlanActionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription_plan(
    payload: SubscriptionPlanCreateRequest,
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> SubscriptionPlanActionResponse:
    return await service.create_plan(payload)


@router.patch('/plans/{plan_id}', response_model=SubscriptionPlanActionResponse)
async def update_subscription_plan(
    plan_id: str,
    payload: SubscriptionPlanUpdateRequest,
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> SubscriptionPlanActionResponse:
    return await service.update_plan(plan_id, payload)


@router.post('/coupons', response_model=CouponActionResponse, status_code=status.HTTP_201_CREATED)
async def create_coupon(
    payload: CouponCreateRequest,
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> CouponActionResponse:
    return await service.create_coupon(payload)


@router.patch('/coupons/{coupon_id}', response_model=CouponActionResponse)
async def update_coupon(
    coupon_id: str,
    payload: CouponUpdateRequest,
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> CouponActionResponse:
    return await service.update_coupon(coupon_id, payload)


@router.post('/coupons/{coupon_id}/activate', response_model=CouponActionResponse)
async def activate_coupon(
    coupon_id: str,
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> CouponActionResponse:
    return await service.activate_coupon(coupon_id)


@router.post('/coupons/{coupon_id}/pause', response_model=CouponActionResponse)
async def pause_coupon(
    coupon_id: str,
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> CouponActionResponse:
    return await service.pause_coupon(coupon_id)


@router.delete('/coupons/{coupon_id}', response_model=SubscriptionActionResponse)
async def delete_coupon(
    coupon_id: str,
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> SubscriptionActionResponse:
    return await service.delete_coupon(coupon_id)
