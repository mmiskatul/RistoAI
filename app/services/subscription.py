from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

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
