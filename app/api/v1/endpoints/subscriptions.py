from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request

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
    SubscriptionPlanManagementResponse,
    SubscriptionPlanUpdateRequest,
    StripeWebhookResponse,
    UserCurrentSubscriptionResponse,
    UserSubscriptionDiscountPreviewRequest,
    UserSubscriptionDiscountPreviewResponse,
    UserSubscriptionActionResponse,
    UserSubscriptionCheckoutSessionResponse,
    UserSubscriptionPortalResponse,
    UserSubscriptionPlanListResponse,
    UserSubscriptionSelectRequest,
)
from app.services.subscription import SubscriptionService

router = APIRouter()


@router.get('/overview', response_model=SubscriptionOverviewResponse, tags=['Subscription Management'])
async def get_subscription_overview(
    query: SubscriptionOverviewQuery = Depends(),
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> SubscriptionOverviewResponse:
    return await service.get_overview(query)


@router.get('/plans/management', response_model=SubscriptionPlanManagementResponse, tags=['Subscription Management'])
async def get_subscription_plan_management(
    query: CouponQuery = Depends(),
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> SubscriptionPlanManagementResponse:
    return await service.get_plan_management(query)


@router.get('/user/plans', response_model=UserSubscriptionPlanListResponse, tags=['User Subscription'])
async def get_user_subscription_plans(
    current_user: dict = Depends(require_roles(UserRole.RESTAURANT_OWNER, UserRole.MANAGER, UserRole.STAFF)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> UserSubscriptionPlanListResponse:
    return await service.get_user_visible_plans(current_user)


@router.get('/user/current', response_model=UserCurrentSubscriptionResponse, tags=['User Subscription'])
async def get_user_current_subscription(
    current_user: dict = Depends(require_roles(UserRole.RESTAURANT_OWNER, UserRole.MANAGER, UserRole.STAFF)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> UserCurrentSubscriptionResponse:
    return await service.get_user_current_subscription(current_user)


@router.post('/user/discount-preview', response_model=UserSubscriptionDiscountPreviewResponse, tags=['User Subscription'])
async def preview_user_subscription_discount(
    payload: UserSubscriptionDiscountPreviewRequest,
    current_user: dict = Depends(require_roles(UserRole.RESTAURANT_OWNER, UserRole.MANAGER, UserRole.STAFF)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> UserSubscriptionDiscountPreviewResponse:
    return await service.preview_user_discount(current_user, payload)


@router.post('/user/select', response_model=UserSubscriptionActionResponse, tags=['User Subscription'])
async def select_user_subscription_plan(
    payload: UserSubscriptionSelectRequest,
    current_user: dict = Depends(require_roles(UserRole.RESTAURANT_OWNER, UserRole.MANAGER, UserRole.STAFF)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> UserSubscriptionActionResponse:
    return await service.select_user_plan(current_user, payload)


@router.post('/user/checkout-session', response_model=UserSubscriptionCheckoutSessionResponse, tags=['User Subscription'], summary='Create Stripe Checkout Session', description='Creates a Stripe Checkout Session for a restaurant user to start a paid subscription in test or live mode.')
async def create_user_subscription_checkout_session(
    payload: UserSubscriptionSelectRequest,
    current_user: dict = Depends(require_roles(UserRole.RESTAURANT_OWNER, UserRole.MANAGER, UserRole.STAFF)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> UserSubscriptionCheckoutSessionResponse:
    return await service.create_checkout_session(current_user, payload)


@router.post('/user/customer-portal', response_model=UserSubscriptionPortalResponse, tags=['User Subscription'], summary='Create Stripe Customer Portal Session', description='Creates a Stripe billing portal session for the current restaurant user.')
async def create_user_subscription_customer_portal(
    current_user: dict = Depends(require_roles(UserRole.RESTAURANT_OWNER, UserRole.MANAGER, UserRole.STAFF)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> UserSubscriptionPortalResponse:
    return await service.create_customer_portal(current_user)


@router.post('/webhook', response_model=StripeWebhookResponse, include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias='Stripe-Signature'),
    service: SubscriptionService = Depends(get_subscription_service),
) -> StripeWebhookResponse:
    payload = await request.body()
    return await service.handle_stripe_webhook(payload, stripe_signature)


@router.patch('/plans', response_model=SubscriptionPlanActionResponse, tags=['Subscription Management'])
async def update_subscription_plan(
    payload: SubscriptionPlanUpdateRequest,
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> SubscriptionPlanActionResponse:
    return await service.update_plan(payload)


@router.post('/coupons', response_model=CouponActionResponse, status_code=201, tags=['Subscription Management'])
async def create_coupon(
    payload: CouponCreateRequest,
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> CouponActionResponse:
    return await service.create_coupon(payload)


@router.patch('/coupons/{coupon_id}', response_model=CouponActionResponse, tags=['Subscription Management'])
async def update_coupon(
    coupon_id: str,
    payload: CouponUpdateRequest,
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> CouponActionResponse:
    return await service.update_coupon(coupon_id, payload)


@router.post('/coupons/{coupon_id}/activate', response_model=CouponActionResponse, tags=['Subscription Management'])
async def activate_coupon(
    coupon_id: str,
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> CouponActionResponse:
    return await service.activate_coupon(coupon_id)


@router.post('/coupons/{coupon_id}/pause', response_model=CouponActionResponse, tags=['Subscription Management'])
async def pause_coupon(
    coupon_id: str,
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> CouponActionResponse:
    return await service.pause_coupon(coupon_id)


@router.delete('/coupons/{coupon_id}', response_model=SubscriptionActionResponse, tags=['Subscription Management'])
async def delete_coupon(
    coupon_id: str,
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: SubscriptionService = Depends(get_subscription_service),
) -> SubscriptionActionResponse:
    return await service.delete_coupon(coupon_id)
