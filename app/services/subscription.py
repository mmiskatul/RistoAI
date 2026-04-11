from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.enums import CouponStatus, SubscriptionPlan, SubscriptionStatus
from app.core.exceptions import ConflictException, ValidationException
from app.repositories.coupon import CouponRepository
from app.repositories.subscription_plan import SubscriptionPlanRepository
from app.repositories.user import UserRepository
from app.repositories.user_subscription import UserSubscriptionRepository
from app.services.stripe_billing import StripeBillingService
from app.schemas.subscription import (
    CouponActionResponse,
    CouponCreateRequest,
    CouponFormFieldResponse,
    CouponListResponse,
    CouponTableColumnResponse,
    CouponQuery,
    CouponResponse,
    CouponUpdateRequest,
    SubscriptionActionResponse,
    SubscriptionFilterChipResponse,
    SubscriptionOverviewQuery,
    SubscriptionOverviewResponse,
    SubscriptionPlanActionResponse,
    SubscriptionPlanDisplayResponse,
    SubscriptionPlanManagementActionResponse,
    SubscriptionPlanManagementResponse,
    SubscriptionPlanResponse,
    SubscriptionPlanUpdateRequest,
    SubscriptionRevenuePointResponse,
    SubscriptionSummaryCardResponse,
    SubscriptionSummaryResponse,
    SubscriptionTableColumnResponse,
    SubscriptionTableItemResponse,
    SubscriptionRowActionResponse,
    UserCurrentSubscriptionResponse,
    UserSubscriptionDiscountPreviewRequest,
    UserSubscriptionDiscountPreviewResponse,
    UserSubscriptionActionResponse,
    UserSubscriptionCheckoutSessionResponse,
    UserSubscriptionPlanListResponse,
    UserSubscriptionPlanResponse,
    UserSubscriptionPortalResponse,
    UserSubscriptionSelectRequest,
    StripeWebhookResponse,
)
from app.services.base import BaseService
from app.utils.pagination import build_pagination_meta


class SubscriptionService(BaseService):
    def __init__(
        self,
        user_repository: UserRepository,
        subscription_plan_repository: SubscriptionPlanRepository,
        coupon_repository: CouponRepository,
        user_subscription_repository: UserSubscriptionRepository,
        stripe_billing_service: StripeBillingService | None = None,
    ) -> None:
        self.user_repository = user_repository
        self.subscription_plan_repository = subscription_plan_repository
        self.coupon_repository = coupon_repository
        self.user_subscription_repository = user_subscription_repository
        self.stripe_billing_service = stripe_billing_service

    async def get_overview(self, query: SubscriptionOverviewQuery) -> SubscriptionOverviewResponse:
        users, total = await self.user_repository.get_filtered_subscription_users(
            search=query.search,
            subscription_status=query.status,
            billing_cycle=query.billing_cycle,
            page=query.page,
            page_size=query.page_size,
        )
        all_subscription_users = await self.user_repository.get_users_with_subscription_data()
        plan_map = await self._get_plan_map()
        pagination = build_pagination_meta(total=total, page=query.page, page_size=query.page_size)

        active_users = [user for user in all_subscription_users if user.get('subscription_status') == SubscriptionStatus.ACTIVE]
        trial_users = [user for user in all_subscription_users if user.get('subscription_status') == SubscriptionStatus.TRIAL]
        summary = SubscriptionSummaryResponse(
            active_subscriptions=len(active_users),
            trial_users=len(trial_users),
            monthly_revenue_mrr=round(sum(self._monthly_revenue_value(user, plan_map) for user in active_users), 2),
            annual_revenue=round(sum(self._annual_revenue_value(user, plan_map) for user in active_users), 2),
        )

        return SubscriptionOverviewResponse(
            summary=summary,
            revenue_chart=self._build_revenue_chart(all_subscription_users, plan_map, query.months),
            items=[self._to_subscription_item(user) for user in users],
            **pagination,
        )

    async def get_plan_management(self, query: CouponQuery) -> SubscriptionPlanManagementResponse:
        await self.coupon_repository.mark_expired_coupons()
        plans = await self.subscription_plan_repository.get_active_plans()
        coupons, total = await self.coupon_repository.get_filtered_coupons(
            search=query.search,
            status=query.status,
            page=query.page,
            page_size=query.page_size,
        )
        pagination = build_pagination_meta(total=total, page=query.page, page_size=query.page_size)
        serialized_plans = [self._to_plan_response(plan) for plan in plans]
        active_plan = self._to_active_plan_display(plans[0]) if plans else None
        return SubscriptionPlanManagementResponse(
            plan=serialized_plans[0] if serialized_plans else None,
            active_plan=active_plan,
            plans=serialized_plans,
            coupons=CouponListResponse(items=[self._to_coupon_response(coupon) for coupon in coupons], **pagination),
        )

    async def get_user_visible_plans(self, current_user: dict) -> UserSubscriptionPlanListResponse:
        plans = await self.subscription_plan_repository.get_visible_plans()
        return UserSubscriptionPlanListResponse(
            selection_required=self._selection_required(current_user),
            plans=[self._to_user_plan_response(plan) for plan in plans],
            current_subscription=self._to_user_current_subscription(current_user),
        )

    async def get_user_current_subscription(self, current_user: dict) -> UserCurrentSubscriptionResponse:
        return self._to_user_current_subscription(current_user)

    async def preview_user_discount(
        self,
        current_user: dict,
        payload: UserSubscriptionDiscountPreviewRequest,
    ) -> UserSubscriptionDiscountPreviewResponse:
        del current_user
        plan = await self._get_single_visible_plan()
        pricing = await self._resolve_coupon_pricing(plan, payload.billing_cycle, payload.coupon_code)
        return UserSubscriptionDiscountPreviewResponse(
            coupon_code=pricing['coupon_code'],
            original_amount=pricing['original_amount'],
            discount_amount=pricing['discount_amount'],
            final_amount=pricing['final_amount'],
        )

    async def select_user_plan(self, current_user: dict, payload: UserSubscriptionSelectRequest) -> UserSubscriptionActionResponse:
        plan = await self._get_single_visible_plan()

        now = datetime.now(UTC)
        if payload.start_trial and plan.get('trial_days', 0) > 0:
            status = SubscriptionStatus.TRIAL
            expires_at = now + timedelta(days=plan['trial_days'])
        else:
            status = SubscriptionStatus.ACTIVE
            expires_at = now + (timedelta(days=365) if payload.billing_cycle == SubscriptionPlan.ONE_YEAR else timedelta(days=30))

        amount = float(plan['annual_price']) if payload.billing_cycle == SubscriptionPlan.ONE_YEAR else float(plan['monthly_price'])

        await self.user_subscription_repository.close_current_for_user(
            str(current_user['_id']),
            ended_at=now,
            final_status=SubscriptionStatus.CANCELED,
        )

        updated_user = await self.user_repository.update(
            current_user['_id'],
            {
                'subscription_plan_name': plan['name'],
                'subscription_plan': payload.billing_cycle,
                'subscription_status': status,
                'subscription_started_at': now,
                'subscription_expires_at': expires_at,
            },
        )
        await self.user_subscription_repository.create(
            {
                'user_id': current_user['_id'],
                'subscription_plan_id': plan['_id'],
                'plan_name': plan['name'],
                'billing_cycle': payload.billing_cycle,
                'status': status,
                'start_trial': payload.start_trial,
                'trial_days': int(plan.get('trial_days', 0)),
                'amount': amount,
                'is_current': True,
                'started_at': now,
                'ended_at': None,
                'expires_at': expires_at,
            }
        )
        return UserSubscriptionActionResponse(
            message='Subscription plan selected successfully',
            subscription=self._to_user_current_subscription(updated_user),
        )

    async def create_checkout_session(self, current_user: dict, payload: UserSubscriptionSelectRequest) -> UserSubscriptionCheckoutSessionResponse:
        if self.stripe_billing_service is None:
            raise ValidationException('Stripe billing is not available')
        plan = await self._get_single_visible_plan()
        customer_id = current_user.get('stripe_customer_id')
        if not customer_id:
            customer = await self.stripe_billing_service.create_customer(
                email=current_user['email'],
                name=current_user['full_name'],
                metadata={'user_id': str(current_user['_id'])},
            )
            customer_id = customer['id']
            await self.user_repository.update(current_user['_id'], {'stripe_customer_id': customer_id})
        session = await self.stripe_billing_service.create_checkout_session(
            customer_id=customer_id,
            billing_cycle=payload.billing_cycle,
            metadata={
                'user_id': str(current_user['_id']),
                'billing_cycle': str(payload.billing_cycle),
                'plan_name': str(plan['name']),
            },
            trial_days=int(plan.get('trial_days', 0)) if payload.start_trial else 0,
        )
        return UserSubscriptionCheckoutSessionResponse(
            session_id=session['id'],
            checkout_url=session['url'],
            publishable_key=getattr(self.stripe_billing_service.settings, 'stripe_publishable_key', None),
        )

    async def create_customer_portal(self, current_user: dict) -> UserSubscriptionPortalResponse:
        if self.stripe_billing_service is None:
            raise ValidationException('Stripe billing is not available')
        customer_id = current_user.get('stripe_customer_id')
        if not customer_id:
            raise ValidationException('Stripe customer does not exist for this user')
        session = await self.stripe_billing_service.create_customer_portal_session(customer_id=customer_id)
        return UserSubscriptionPortalResponse(portal_url=session['url'])

    async def handle_stripe_webhook(self, payload: bytes, signature: str | None) -> StripeWebhookResponse:
        if self.stripe_billing_service is None:
            raise ValidationException('Stripe billing is not available')
        event = self.stripe_billing_service.construct_event(payload, signature)
        event_type = event['type']
        data = event['data']['object']

        if event_type == 'checkout.session.completed' and data.get('subscription'):
            await self._sync_stripe_subscription(user_id=data.get('metadata', {}).get('user_id'), stripe_subscription_id=data['subscription'], stripe_customer_id=data.get('customer'))
        elif event_type in {'customer.subscription.created', 'customer.subscription.updated', 'customer.subscription.deleted'}:
            await self._sync_stripe_subscription_object(data)
        elif event_type == 'invoice.paid' and data.get('subscription'):
            await self._sync_stripe_subscription(user_id=None, stripe_subscription_id=data['subscription'], stripe_customer_id=data.get('customer'))
        elif event_type == 'invoice.payment_failed' and data.get('subscription'):
            await self._mark_failed_subscription(data['subscription'])

        return StripeWebhookResponse(received=True, event_type=event_type)


    async def _sync_stripe_subscription(
        self,
        *,
        user_id: str | None,
        stripe_subscription_id: str,
        stripe_customer_id: str | None = None,
    ) -> None:
        if self.stripe_billing_service is None:
            return
        subscription = await self.stripe_billing_service.retrieve_subscription(stripe_subscription_id)
        if stripe_customer_id and not subscription.get('customer'):
            subscription['customer'] = stripe_customer_id
        metadata = subscription.get('metadata') or {}
        if user_id and not metadata.get('user_id'):
            metadata['user_id'] = user_id
            subscription['metadata'] = metadata
        await self._sync_stripe_subscription_object(subscription)

    async def _sync_stripe_subscription_object(self, subscription: dict[str, Any]) -> None:
        metadata = subscription.get('metadata') or {}
        user = None
        user_id = metadata.get('user_id')
        if user_id:
            user = await self.user_repository.get_by_id(user_id)
        if user is None and subscription.get('customer'):
            user = await self.user_repository.get_by_stripe_customer_id(str(subscription['customer']))
        if user is None and subscription.get('id'):
            user = await self.user_repository.get_by_stripe_subscription_id(str(subscription['id']))
        if user is None:
            return

        started_at = self._from_unix_timestamp(subscription.get('current_period_start'))
        expires_at = self._from_unix_timestamp(subscription.get('current_period_end'))
        price_id = self._extract_price_id(subscription)
        billing_cycle = self._billing_cycle_from_price_id(price_id)
        status = self._map_stripe_status(subscription.get('status'))

        plan_name = metadata.get('plan_name') or user.get('subscription_plan_name')
        if not plan_name:
            plan = await self._get_single_visible_plan()
            plan_name = str(plan['name'])

        user_updates = {
            'stripe_customer_id': subscription.get('customer'),
            'stripe_subscription_id': subscription.get('id'),
            'stripe_price_id': price_id,
            'subscription_plan_name': plan_name,
            'subscription_plan': billing_cycle,
            'subscription_status': status,
            'subscription_started_at': started_at,
            'subscription_expires_at': expires_at,
        }
        updated_user = await self.user_repository.update(user['_id'], user_updates)

        current_subscription = await self.user_subscription_repository.get_current_by_stripe_subscription_id(str(subscription['id']))
        payload = {
            'user_id': updated_user['_id'],
            'subscription_plan_id': None,
            'plan_name': plan_name,
            'billing_cycle': billing_cycle,
            'status': status,
            'start_trial': status == SubscriptionStatus.TRIAL,
            'trial_days': 0,
            'amount': 0.0,
            'is_current': status != SubscriptionStatus.CANCELED,
            'started_at': started_at,
            'ended_at': None if status != SubscriptionStatus.CANCELED else datetime.now(UTC),
            'expires_at': expires_at,
            'payment_provider': 'stripe',
            'stripe_checkout_session_id': None,
            'stripe_subscription_id': subscription.get('id'),
            'stripe_customer_id': subscription.get('customer'),
            'stripe_price_id': price_id,
            'stripe_invoice_id': None,
        }
        if current_subscription:
            await self.user_subscription_repository.update(current_subscription['_id'], payload)
        else:
            await self.user_subscription_repository.close_current_for_user(
                str(updated_user['_id']),
                ended_at=datetime.now(UTC),
                final_status=SubscriptionStatus.CANCELED,
            )
            await self.user_subscription_repository.create(payload)

    async def _mark_failed_subscription(self, stripe_subscription_id: str) -> None:
        user = await self.user_repository.get_by_stripe_subscription_id(stripe_subscription_id)
        if user is not None:
            await self.user_repository.update(
                user['_id'],
                {'subscription_status': SubscriptionStatus.SUSPENDED},
            )
        current_subscription = await self.user_subscription_repository.get_current_by_stripe_subscription_id(stripe_subscription_id)
        if current_subscription is not None:
            await self.user_subscription_repository.update(
                current_subscription['_id'],
                {'status': SubscriptionStatus.SUSPENDED},
            )

    def _extract_price_id(self, subscription: dict[str, Any]) -> str | None:
        items = subscription.get('items', {}).get('data') or []
        if not items:
            return None
        return items[0].get('price', {}).get('id')

    def _billing_cycle_from_price_id(self, price_id: str | None) -> SubscriptionPlan:
        settings = getattr(self.stripe_billing_service, 'settings', None)
        yearly_price_id = getattr(settings, 'stripe_price_id_yearly', None) if settings else None
        if yearly_price_id and price_id == yearly_price_id:
            return SubscriptionPlan.ONE_YEAR
        return SubscriptionPlan.ONE_MONTH

    @staticmethod
    def _from_unix_timestamp(value: Any) -> datetime | None:
        if value in (None, ''):
            return None
        try:
            return datetime.fromtimestamp(int(value), tz=UTC)
        except (TypeError, ValueError, OSError):
            return None

    @staticmethod
    def _map_stripe_status(value: str | None) -> SubscriptionStatus:
        mapping = {
            'trialing': SubscriptionStatus.TRIAL,
            'active': SubscriptionStatus.ACTIVE,
            'past_due': SubscriptionStatus.SUSPENDED,
            'unpaid': SubscriptionStatus.SUSPENDED,
            'paused': SubscriptionStatus.SUSPENDED,
            'canceled': SubscriptionStatus.CANCELED,
            'incomplete_expired': SubscriptionStatus.EXPIRED,
            'incomplete': SubscriptionStatus.SUSPENDED,
        }
        return mapping.get(str(value), SubscriptionStatus.ACTIVE)

    async def update_plan(self, payload: SubscriptionPlanUpdateRequest) -> SubscriptionPlanActionResponse:
        updates = payload.model_dump(exclude_none=True, mode='json')
        if not updates:
            raise ValidationException('No fields provided for update')
        plan = await self.subscription_plan_repository.get_plan()
        updated_plan = await self.subscription_plan_repository.update(plan['_id'], updates)
        return SubscriptionPlanActionResponse(message='Subscription plan updated successfully', plan=self._to_plan_response(updated_plan))

    async def create_coupon(self, payload: CouponCreateRequest) -> CouponActionResponse:
        existing_coupon = await self.coupon_repository.get_by_code(payload.code)
        if existing_coupon:
            raise ConflictException('A coupon with this code already exists')
        coupon = await self.coupon_repository.create(
            {
                **payload.model_dump(mode='json'),
                'code': payload.code.upper(),
                'usage_count': 0,
            }
        )
        return CouponActionResponse(message='Coupon created successfully', coupon=self._to_coupon_response(coupon))

    async def update_coupon(self, coupon_id: str, payload: CouponUpdateRequest) -> CouponActionResponse:
        updates = payload.model_dump(exclude_none=True, mode='json')
        if not updates:
            raise ValidationException('No fields provided for update')
        coupon = await self.coupon_repository.update(coupon_id, updates)
        return CouponActionResponse(message='Coupon updated successfully', coupon=self._to_coupon_response(coupon))

    async def activate_coupon(self, coupon_id: str) -> CouponActionResponse:
        coupon = await self.coupon_repository.update(coupon_id, {'status': CouponStatus.ACTIVE})
        return CouponActionResponse(message='Coupon activated successfully', coupon=self._to_coupon_response(coupon))

    async def pause_coupon(self, coupon_id: str) -> CouponActionResponse:
        coupon = await self.coupon_repository.update(coupon_id, {'status': CouponStatus.PAUSED})
        return CouponActionResponse(message='Coupon paused successfully', coupon=self._to_coupon_response(coupon))

    async def delete_coupon(self, coupon_id: str) -> SubscriptionActionResponse:
        await self.coupon_repository.delete(coupon_id)
        return SubscriptionActionResponse(message='Coupon deleted successfully')

    async def _get_single_visible_plan(self) -> dict:
        plans = await self.subscription_plan_repository.get_visible_plans()
        if not plans:
            raise ValidationException('No subscription plan is available')
        return plans[0]

    async def _resolve_coupon_pricing(self, plan: dict, billing_cycle: SubscriptionPlan, coupon_code: str) -> dict:
        await self.coupon_repository.mark_expired_coupons()
        coupon = await self.coupon_repository.get_by_code(coupon_code)
        if not coupon:
            raise ValidationException('Coupon is not valid')
        if coupon.get('status') != CouponStatus.ACTIVE:
            raise ValidationException('Coupon is not valid')
        if coupon.get('usage_count', 0) >= coupon.get('usage_limit', 0):
            raise ValidationException('Coupon is not valid')

        original_amount = float(plan['annual_price']) if billing_cycle == SubscriptionPlan.ONE_YEAR else float(plan['monthly_price'])
        if coupon['discount_type'] == 'percentage':
            discount_amount = round(original_amount * (float(coupon['value']) / 100), 2)
        else:
            discount_amount = min(float(coupon['value']), original_amount)
        return {
            'coupon_code': str(coupon['code']),
            'original_amount': original_amount,
            'discount_amount': discount_amount,
            'final_amount': round(max(original_amount - discount_amount, 0.0), 2),
        }

    async def _get_plan_map(self) -> dict[str, dict]:
        plans = await self.subscription_plan_repository.get_active_plans()
        return {plan['name']: plan for plan in plans}

    def _monthly_revenue_value(self, user: dict, plan_map: dict[str, dict]) -> float:
        plan = plan_map.get(user.get('subscription_plan_name'))
        if not plan:
            return 0.0
        if user.get('subscription_plan') == SubscriptionPlan.ONE_YEAR:
            return float(plan['annual_price']) / 12
        return float(plan['monthly_price'])

    def _annual_revenue_value(self, user: dict, plan_map: dict[str, dict]) -> float:
        plan = plan_map.get(user.get('subscription_plan_name'))
        if not plan:
            return 0.0
        if user.get('subscription_plan') == SubscriptionPlan.ONE_YEAR:
            return float(plan['annual_price'])
        return float(plan['monthly_price']) * 12

    def _build_revenue_chart(
        self,
        users: list[dict],
        plan_map: dict[str, dict],
        months: int,
    ) -> list[SubscriptionRevenuePointResponse]:
        now = datetime.now(UTC)
        labels: list[tuple[int, int, str]] = []
        year = now.year
        month = now.month
        for _ in range(months):
            labels.append((year, month, datetime(year, month, 1, tzinfo=UTC).strftime('%b').upper()))
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        labels.reverse()

        totals: dict[tuple[int, int], float] = defaultdict(float)
        for user in users:
            if user.get('subscription_status') == SubscriptionStatus.TRIAL:
                continue
            started_at = user.get('subscription_started_at')
            if not started_at:
                continue
            totals[(started_at.year, started_at.month)] += self._charge_value(user, plan_map)

        return [
            SubscriptionRevenuePointResponse(label=label, value=round(totals[(year, month)], 2))
            for year, month, label in labels
        ]

    def _charge_value(self, user: dict, plan_map: dict[str, dict]) -> float:
        plan = plan_map.get(user.get('subscription_plan_name'))
        if not plan:
            return 0.0
        if user.get('subscription_plan') == SubscriptionPlan.ONE_YEAR:
            return float(plan['annual_price'])
        return float(plan['monthly_price'])

    def _to_subscription_item(self, user: dict) -> SubscriptionTableItemResponse:
        serialized = self.serialize(user)
        status = serialized.get('subscription_status')
        return SubscriptionTableItemResponse(
            user_id=serialized['id'],
            full_name=serialized['full_name'],
            email=serialized['email'],
            restaurant_name=serialized.get('restaurant_name'),
            plan_name=serialized.get('subscription_plan_name'),
            billing_cycle=serialized.get('subscription_plan'),
            status=status,
            start_date=serialized.get('subscription_started_at'),
            next_billing=self._resolve_next_billing(serialized),
        )

    def _resolve_next_billing(self, user: dict) -> datetime | None:
        if user.get('subscription_status') in {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL}:
            return user.get('subscription_expires_at')
        return None

    def _to_plan_response(self, plan: dict) -> SubscriptionPlanResponse:
        serialized = self.serialize(plan)
        serialized.pop('singleton_key', None)
        return SubscriptionPlanResponse(**serialized)

    def _to_coupon_response(self, coupon: dict) -> CouponResponse:
        serialized = self.serialize(coupon)
        return CouponResponse(**serialized)

    def _to_user_plan_response(self, plan: dict) -> UserSubscriptionPlanResponse:
        serialized = self.serialize(plan)
        return UserSubscriptionPlanResponse(
            id=serialized['id'],
            name=serialized['name'],
            monthly_price=serialized['monthly_price'],
            annual_price=serialized['annual_price'],
            trial_days=serialized['trial_days'],
            features=serialized['features'],
            is_best_plan=serialized['is_best_plan'],
        )

    def _to_user_current_subscription(self, user: dict) -> UserCurrentSubscriptionResponse:
        serialized = self.serialize(user)
        return UserCurrentSubscriptionResponse(
            selection_required=self._selection_required(user),
            plan_name=serialized.get('subscription_plan_name'),
            billing_cycle=serialized.get('subscription_plan'),
            status=serialized.get('subscription_status'),
            started_at=serialized.get('subscription_started_at'),
            expires_at=serialized.get('subscription_expires_at'),
        )

    @staticmethod
    def _selection_required(user: dict) -> bool:
        return not bool(user.get('subscription_plan_name'))
    def _to_active_plan_display(self, plan: dict) -> SubscriptionPlanDisplayResponse:
        serialized = self.serialize(plan)
        return SubscriptionPlanDisplayResponse(
            id=serialized['id'],
            name=serialized['name'],
            monthly_price=serialized['monthly_price'],
            annual_price=serialized['annual_price'],
            features=serialized['features'],
            visibility_enabled=bool(serialized['is_visible']),
        )
