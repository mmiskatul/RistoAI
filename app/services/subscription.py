from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from app.core.enums import CouponStatus, SubscriptionPlan, SubscriptionStatus
from app.core.exceptions import ConflictException, ValidationException
from app.repositories.coupon import CouponRepository
from app.repositories.subscription_plan import SubscriptionPlanRepository
from app.repositories.user import UserRepository
from app.schemas.subscription import (
    CouponActionResponse,
    CouponCreateRequest,
    CouponListResponse,
    CouponQuery,
    CouponResponse,
    CouponUpdateRequest,
    SubscriptionActionResponse,
    SubscriptionOverviewQuery,
    SubscriptionOverviewResponse,
    SubscriptionPlanActionResponse,
    SubscriptionPlanCreateRequest,
    SubscriptionPlanManagementResponse,
    SubscriptionPlanResponse,
    SubscriptionPlanUpdateRequest,
    SubscriptionRevenuePointResponse,
    SubscriptionSummaryResponse,
    SubscriptionTableItemResponse,
    UserCurrentSubscriptionResponse,
    UserSubscriptionActionResponse,
    UserSubscriptionPlanListResponse,
    UserSubscriptionPlanResponse,
    UserSubscriptionSelectRequest,
)
from app.services.base import BaseService
from app.utils.pagination import build_pagination_meta


class SubscriptionService(BaseService):
    def __init__(
        self,
        user_repository: UserRepository,
        subscription_plan_repository: SubscriptionPlanRepository,
        coupon_repository: CouponRepository,
    ) -> None:
        self.user_repository = user_repository
        self.subscription_plan_repository = subscription_plan_repository
        self.coupon_repository = coupon_repository

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

        return SubscriptionOverviewResponse(
            summary=SubscriptionSummaryResponse(
                active_subscriptions=len(active_users),
                trial_users=len(trial_users),
                monthly_revenue_mrr=round(sum(self._monthly_revenue_value(user, plan_map) for user in active_users), 2),
                annual_revenue=round(sum(self._annual_revenue_value(user, plan_map) for user in active_users), 2),
            ),
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
        return SubscriptionPlanManagementResponse(
            plans=[self._to_plan_response(plan) for plan in plans],
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

    async def select_user_plan(self, current_user: dict, payload: UserSubscriptionSelectRequest) -> UserSubscriptionActionResponse:
        plan = await self.subscription_plan_repository.get_by_id(payload.plan_id)
        if not plan.get('is_active', False) or not plan.get('is_visible', False):
            raise ValidationException('Selected plan is not available')

        now = datetime.now(UTC)
        if payload.start_trial and plan.get('trial_days', 0) > 0:
            status = SubscriptionStatus.TRIAL
            expires_at = now + timedelta(days=plan['trial_days'])
        else:
            status = SubscriptionStatus.ACTIVE
            expires_at = now + (timedelta(days=365) if payload.billing_cycle == SubscriptionPlan.ONE_YEAR else timedelta(days=30))

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
        return UserSubscriptionActionResponse(
            message='Subscription plan selected successfully',
            subscription=self._to_user_current_subscription(updated_user),
        )

    async def create_plan(self, payload: SubscriptionPlanCreateRequest) -> SubscriptionPlanActionResponse:
        existing_plan = await self.subscription_plan_repository.get_by_name(payload.name)
        if existing_plan:
            raise ConflictException('A subscription plan with this name already exists')
        plan = await self.subscription_plan_repository.create(payload.model_dump(mode='json'))
        return SubscriptionPlanActionResponse(message='Subscription plan created successfully', plan=self._to_plan_response(plan))

    async def update_plan(self, plan_id: str, payload: SubscriptionPlanUpdateRequest) -> SubscriptionPlanActionResponse:
        updates = payload.model_dump(exclude_none=True, mode='json')
        if not updates:
            raise ValidationException('No fields provided for update')
        if 'name' in updates:
            existing_plan = await self.subscription_plan_repository.get_by_name(updates['name'])
            if existing_plan and str(existing_plan['_id']) != plan_id:
                raise ConflictException('A subscription plan with this name already exists')
        plan = await self.subscription_plan_repository.update(plan_id, updates)
        return SubscriptionPlanActionResponse(message='Subscription plan updated successfully', plan=self._to_plan_response(plan))

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
        return SubscriptionTableItemResponse(
            user_id=serialized['id'],
            full_name=serialized['full_name'],
            email=serialized['email'],
            restaurant_name=serialized.get('restaurant_name'),
            plan_name=serialized.get('subscription_plan_name'),
            billing_cycle=serialized.get('subscription_plan'),
            status=serialized.get('subscription_status'),
            start_date=serialized.get('subscription_started_at'),
            next_billing=self._resolve_next_billing(serialized),
        )

    def _resolve_next_billing(self, user: dict) -> datetime | None:
        if user.get('subscription_status') in {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL}:
            return user.get('subscription_expires_at')
        return None

    def _to_plan_response(self, plan: dict) -> SubscriptionPlanResponse:
        serialized = self.serialize(plan)
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
