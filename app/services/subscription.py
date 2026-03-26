from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from app.core.enums import CouponStatus, SubscriptionPlan, SubscriptionStatus
from app.core.exceptions import ConflictException, ValidationException
from app.repositories.coupon import CouponRepository
from app.repositories.subscription_plan import SubscriptionPlanRepository
from app.repositories.user import UserRepository
from app.repositories.user_subscription import UserSubscriptionRepository
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
        user_subscription_repository: UserSubscriptionRepository,
    ) -> None:
        self.user_repository = user_repository
        self.subscription_plan_repository = subscription_plan_repository
        self.coupon_repository = coupon_repository
        self.user_subscription_repository = user_subscription_repository

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
            filter_chips=[
                SubscriptionFilterChipResponse(key='all', label='All'),
                SubscriptionFilterChipResponse(key='active', label='Active'),
                SubscriptionFilterChipResponse(key='trial', label='Trial'),
                SubscriptionFilterChipResponse(key='canceled', label='Canceled'),
                SubscriptionFilterChipResponse(key='expired', label='Expired'),
            ],
            summary_cards=[
                SubscriptionSummaryCardResponse(key='active_subscriptions', label='Active Subscriptions', value=summary.active_subscriptions, value_formatted=f"{summary.active_subscriptions:,}", change_percent=12.0, change_label='+12%', trend='up'),
                SubscriptionSummaryCardResponse(key='trial_users', label='Trial Users', value=summary.trial_users, value_formatted=f"{summary.trial_users:,}", change_percent=5.0, change_label='+5%', trend='up'),
                SubscriptionSummaryCardResponse(key='monthly_revenue_mrr', label='Monthly Revenue (MRR)', value=summary.monthly_revenue_mrr, value_formatted=self._format_currency(summary.monthly_revenue_mrr), change_percent=8.0, change_label='+8%', trend='up'),
                SubscriptionSummaryCardResponse(key='annual_revenue', label='Annual Revenue', value=summary.annual_revenue, value_formatted=self._format_currency(summary.annual_revenue), change_percent=15.0, change_label='+15%', trend='up'),
            ],
            revenue_chart_range_label=f'Last {query.months} months',
            table_columns=[
                SubscriptionTableColumnResponse(key='user_restaurant', label='User & Restaurant'),
                SubscriptionTableColumnResponse(key='plan_name', label='Plan Name'),
                SubscriptionTableColumnResponse(key='billing_cycle', label='Billing Cycle'),
                SubscriptionTableColumnResponse(key='status', label='Status'),
                SubscriptionTableColumnResponse(key='start_date', label='Start Date'),
                SubscriptionTableColumnResponse(key='next_billing', label='Next Billing'),
                SubscriptionTableColumnResponse(key='actions', label='Actions'),
            ],
            pagination_label=f"Showing 1 to {len(users)} of {total:,} entries" if total else 'No subscription entries found',
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
            coupon_form_fields=[
                CouponFormFieldResponse(key='code', label='Coupon Code', input_type='text', placeholder='E.G. SAVE20'),
                CouponFormFieldResponse(key='discount_type', label='Discount Type', input_type='select', options=['Percentage (%)', 'Fixed Amount']),
                CouponFormFieldResponse(key='value', label='Value', input_type='number', placeholder='20'),
                CouponFormFieldResponse(key='expires_at', label='Expiration Date', input_type='date', placeholder='mm/dd/yyyy'),
                CouponFormFieldResponse(key='usage_limit', label='Usage Limit', input_type='number', placeholder='100'),
            ],
            coupon_table_columns=[
                CouponTableColumnResponse(key='code', label='Coupon Code'),
                CouponTableColumnResponse(key='discount', label='Discount'),
                CouponTableColumnResponse(key='usage_count', label='Usage Count'),
                CouponTableColumnResponse(key='expiration_date', label='Expiration Date'),
                CouponTableColumnResponse(key='status', label='Status'),
            ],
            coupon_pagination_label=f"Showing {len(coupons)} of {total} coupons",
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
            user_restaurant_label=serialized['full_name'],
            user_email_label=serialized['email'],
            billing_cycle_label=self._billing_cycle_label(serialized.get('subscription_plan')),
            status_label=self._status_label(status),
            status_color=self._status_color(status),
            start_date_formatted=self._format_subscription_date(serialized.get('subscription_started_at')),
            next_billing_formatted=self._format_subscription_date(self._resolve_next_billing(serialized)),
            actions_menu=self._build_subscription_actions(serialized['id'], status),
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
    @staticmethod
    def _format_currency(value: float) -> str:
        return f"${value:,.2f}"

    @staticmethod
    def _billing_cycle_label(value: str | None) -> str | None:
        if value == SubscriptionPlan.ONE_YEAR:
            return 'YEARLY'
        if value == SubscriptionPlan.ONE_MONTH:
            return 'MONTHLY'
        return None

    @staticmethod
    def _status_label(value: str | None) -> str | None:
        if not value:
            return None
        return str(value).capitalize()

    @staticmethod
    def _status_color(value: str | None) -> str | None:
        return {
            SubscriptionStatus.ACTIVE: 'green',
            SubscriptionStatus.TRIAL: 'blue',
            SubscriptionStatus.CANCELED: 'gray',
            SubscriptionStatus.EXPIRED: 'red',
            SubscriptionStatus.SUSPENDED: 'orange',
        }.get(value)

    @staticmethod
    def _format_subscription_date(value: datetime | str | None) -> str | None:
        if value is None:
            return '-'
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return value.strftime('%b %d, %Y')

    @staticmethod
    def _build_subscription_actions(user_id: str, status: str | None) -> list[SubscriptionRowActionResponse]:
        actions: list[SubscriptionRowActionResponse] = []
        if status == SubscriptionStatus.TRIAL:
            actions.append(SubscriptionRowActionResponse(key='extend_trial', label='Extend Trial', method='PATCH', endpoint=f'/api/v1/users/{user_id}'))
        actions.append(SubscriptionRowActionResponse(key='more', label='More Actions', method='GET', endpoint=f'/api/v1/users/{user_id}'))
        return actions
    def _to_active_plan_display(self, plan: dict) -> SubscriptionPlanDisplayResponse:
        serialized = self.serialize(plan)
        annual_savings_label = None
        if serialized['monthly_price'] > 0 and serialized['annual_price'] > 0:
            monthly_total = serialized['monthly_price'] * 12
            savings_percent = round(((monthly_total - serialized['annual_price']) / monthly_total) * 100) if monthly_total else 0
            annual_savings_label = f"or ${serialized['annual_price']:,.0f} / year (save {savings_percent}%)"
        return SubscriptionPlanDisplayResponse(
            id=serialized['id'],
            name=serialized['name'],
            monthly_price=serialized['monthly_price'],
            monthly_price_formatted=f"${serialized['monthly_price']:,.0f} / month",
            annual_price=serialized['annual_price'],
            annual_price_formatted=f"${serialized['annual_price']:,.0f} / year",
            annual_savings_label=annual_savings_label,
            trial_status_label=f"Trial Status: {serialized['trial_days']} days free trial active for new users",
            features=serialized['features'],
            internal_actions=[
                SubscriptionPlanManagementActionResponse(key='edit_monthly_price', label='Edit Price', method='PATCH', endpoint='/api/v1/subscriptions/plans'),
                SubscriptionPlanManagementActionResponse(key='edit_annual_price', label='Edit Annual Price', method='PATCH', endpoint='/api/v1/subscriptions/plans'),
                SubscriptionPlanManagementActionResponse(key='change_trial_period', label='Change Trial Period', method='PATCH', endpoint='/api/v1/subscriptions/plans'),
            ],
            visibility_enabled=bool(serialized['is_visible']),
        )
