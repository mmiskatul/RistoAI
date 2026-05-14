from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config.settings import get_settings
from app.core.enums import SubscriptionPlan, SubscriptionStatus, UserRole
from app.repositories.auth_code import AuthCodeRepository
from app.repositories.onboarding_profile import OnboardingProfileRepository
from app.repositories.restaurant_ops import (
    RestaurantCashDepositRepository,
    RestaurantInventoryRepository,
    RestaurantRecordRepository,
)
from app.repositories.subscription_plan import SubscriptionPlanRepository
from app.repositories.user import UserRepository
from app.schemas.dashboard import (
    DashboardAnalyticsBreakdownItemResponse,
    DashboardAnalyticsPointResponse,
    DashboardAnalyticsResponse,
    DashboardAnalyticsStatCardResponse,
    DashboardCashRowResponse,
    DashboardChartsResponse,
    DashboardDailyDataRowResponse,
    DashboardInventoryRowResponse,
    DashboardKpiResponse,
    DashboardMetaResponse,
    DashboardMonthlyPointResponse,
    DashboardOverviewResponse,
    DashboardRoleBreakdownResponse,
    DashboardSeriesPointResponse,
    DashboardUserGrowthSliceResponse,
    DashboardUserMetricsResponse,
)
from app.services.base import BaseService

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
ROLE_LABELS = {
    UserRole.SUPER_ADMIN: "Admins",
    UserRole.RESTAURANT_OWNER: "Restaurant Owners",
    UserRole.MANAGER: "Managers",
    UserRole.STAFF: "Staff",
}


class DashboardService(BaseService):
    def __init__(
        self,
        user_repository: UserRepository,
        onboarding_repository: OnboardingProfileRepository,
        auth_code_repository: AuthCodeRepository,
        subscription_plan_repository: SubscriptionPlanRepository,
        record_repository: RestaurantRecordRepository,
        cash_repository: RestaurantCashDepositRepository,
        inventory_repository: RestaurantInventoryRepository,
    ) -> None:
        self.user_repository = user_repository
        self.onboarding_repository = onboarding_repository
        self.auth_code_repository = auth_code_repository
        self.subscription_plan_repository = subscription_plan_repository
        self.record_repository = record_repository
        self.cash_repository = cash_repository
        self.inventory_repository = inventory_repository

    async def get_user_metrics(self) -> DashboardUserMetricsResponse:
        role_counts, total_users, active_users, verified_users = await asyncio.gather(
            self.user_repository.get_role_counts(),
            self.user_repository.count(),
            self.user_repository.count({"is_active": True}),
            self.user_repository.count({"email_verified": True}),
        )

        return DashboardUserMetricsResponse(
            total_users=total_users,
            active_users=active_users,
            verified_users=verified_users,
            admins=role_counts.get(UserRole.SUPER_ADMIN, 0),
            restaurant_owners=role_counts.get(UserRole.RESTAURANT_OWNER, 0),
            managers=role_counts.get(UserRole.MANAGER, 0),
            staff=role_counts.get(UserRole.STAFF, 0),
        )

    async def get_analytics(self, *, range_key: str = "30d") -> DashboardAnalyticsResponse:
        users, plan_map = await asyncio.gather(
            self.user_repository.get_users_with_subscription_data(),
            self._get_plan_map(),
        )
        now = datetime.now(UTC)
        current_range_start = self._range_start(now, range_key)
        previous_range_start = self._range_start(current_range_start - timedelta(seconds=1), range_key)
        previous_range_end = current_range_start

        active_now = sum(1 for user in users if self._is_subscription_active_on(user, now))
        active_previous = sum(1 for user in users if self._is_subscription_active_on(user, previous_range_end))
        trial_now = sum(1 for user in users if user.get("subscription_status") == SubscriptionStatus.TRIAL)
        trial_previous = sum(
            1
            for user in users
            if user.get("subscription_status") == SubscriptionStatus.TRIAL
            and (self._as_utc(user.get("created_at")) or now) < previous_range_end
        )
        total_users = len(users)
        total_users_previous = sum(1 for user in users if (self._as_utc(user.get("created_at")) or now) < previous_range_end)
        monthly_revenue_now = round(
            sum(self._monthly_revenue_value(user, plan_map) for user in users if self._is_subscription_active_on(user, now)),
            2,
        )
        monthly_revenue_previous = round(
            sum(self._monthly_revenue_value(user, plan_map) for user in users if self._is_subscription_active_on(user, previous_range_end)),
            2,
        )
        conversion_now = self._safe_percent(active_now, active_now + trial_now)
        conversion_previous = self._safe_percent(active_previous, active_previous + trial_previous)

        return DashboardAnalyticsResponse(
            range_key=range_key,
            stat_cards=[
                DashboardAnalyticsStatCardResponse(
                    key="total_users",
                    label="Total Users",
                    value=float(total_users),
                    value_formatted=f"{total_users:,}",
                    change_percent=self._change_percent(total_users, total_users_previous),
                    trend="up" if total_users >= total_users_previous else "down",
                ),
                DashboardAnalyticsStatCardResponse(
                    key="active_subscriptions",
                    label="Active Subscriptions",
                    value=float(active_now),
                    value_formatted=f"{active_now:,}",
                    change_percent=self._change_percent(active_now, active_previous),
                    trend="up" if active_now >= active_previous else "down",
                ),
                DashboardAnalyticsStatCardResponse(
                    key="monthly_revenue",
                    label="Monthly Revenue",
                    value=monthly_revenue_now,
                    value_formatted=self._format_currency(monthly_revenue_now),
                    change_percent=self._change_percent(monthly_revenue_now, monthly_revenue_previous),
                    trend="up" if monthly_revenue_now >= monthly_revenue_previous else "down",
                ),
                DashboardAnalyticsStatCardResponse(
                    key="trial_conversion",
                    label="Trial Conversion",
                    value=conversion_now,
                    value_formatted=f"{conversion_now:.1f}%",
                    change_percent=self._change_percent(conversion_now, conversion_previous),
                    trend="up" if conversion_now >= conversion_previous else "down",
                ),
            ],
            user_growth=self._build_analytics_user_growth(users, range_key=range_key, now=now),
            revenue_growth=self._build_analytics_revenue_growth(users, plan_map=plan_map, range_key=range_key, now=now),
            subscription_status=self._build_analytics_subscription_status(users),
            billing_cycle=self._build_analytics_billing_cycle(users),
        )

    async def get_overview(self, current_user: dict, year: int | None = None) -> DashboardOverviewResponse:
        selected_year = year or datetime.now(UTC).year
        del current_user
        (
            role_counts,
            total_users,
            active_users,
            verified_users,
            completed_onboarding,
            pending_verifications,
            monthly_new_users,
            monthly_completed_onboarding,
            subscription_users,
            plan_map,
        ) = await asyncio.gather(
            self.user_repository.get_role_counts(),
            self.user_repository.count(),
            self.user_repository.count({"is_active": True}),
            self.user_repository.count({"email_verified": True}),
            self.onboarding_repository.count_completed(),
            self.auth_code_repository.count_pending(purpose="restaurant_registration"),
            self.user_repository.get_monthly_registrations(selected_year),
            self.onboarding_repository.get_monthly_completed_counts(selected_year),
            self.user_repository.get_users_with_subscription_data(),
            self._get_plan_map(),
        )

        active_subscriptions = sum(1 for user in subscription_users if user.get("subscription_status") == SubscriptionStatus.ACTIVE)
        trial_users = sum(1 for user in subscription_users if user.get("subscription_status") == SubscriptionStatus.TRIAL)
        monthly_revenue = round(
            sum(self._monthly_revenue_value(user, plan_map) for user in subscription_users if user.get("subscription_status") == SubscriptionStatus.ACTIVE),
            2,
        )

        summary = DashboardKpiResponse(
            total_users=total_users,
            active_users=active_users,
            verified_users=verified_users,
            completed_onboarding=completed_onboarding,
            pending_verifications=pending_verifications,
            active_subscriptions=active_subscriptions,
            trial_users=trial_users,
            monthly_revenue=monthly_revenue,
            admins=role_counts.get(UserRole.SUPER_ADMIN, 0),
            restaurant_owners=role_counts.get(UserRole.RESTAURANT_OWNER, 0),
            managers=role_counts.get(UserRole.MANAGER, 0),
            staff=role_counts.get(UserRole.STAFF, 0),
        )
        charts = DashboardChartsResponse(
            monthly_new_users=self._build_monthly_points(monthly_new_users),
            monthly_completed_onboarding=self._build_monthly_points(monthly_completed_onboarding),
            monthly_revenue=self._build_monthly_revenue_points(subscription_users, plan_map, selected_year),
            weekly_revenue=self._build_weekly_revenue_points(subscription_users, plan_map, selected_year),
            users_by_role=self._build_role_breakdown(role_counts),
            subscription_breakdown=self._build_subscription_breakdown(active_subscriptions, trial_users),
        )
        restaurant_lookup = await self.user_repository.get_restaurant_lookup()
        recent_daily_data, recent_cash_deposits, recent_inventory_items = await asyncio.gather(
            self._get_recent_daily_data_rows(restaurant_lookup),
            self._get_recent_cash_rows(restaurant_lookup),
            self._get_recent_inventory_rows(restaurant_lookup),
        )

        return DashboardOverviewResponse(
            summary=summary,
            charts=charts,
            meta=DashboardMetaResponse(year=selected_year),
            recent_daily_data=recent_daily_data,
            recent_cash_deposits=recent_cash_deposits,
            recent_inventory_items=recent_inventory_items,
        )

    async def _get_recent_daily_data_rows(self, restaurant_lookup: dict[str, str]) -> list[DashboardDailyDataRowResponse]:
        rows = await self.record_repository.collection.find(
            {"period_type": "day"},
            {
                "_id": 1,
                "tenant_id": 1,
                "business_date": 1,
                "total_revenue": 1,
                "total_expenses": 1,
                "total_covers": 1,
                "updated_at": 1,
            },
        ).sort([("business_date", -1), ("updated_at", -1)]).limit(6).to_list(length=6)
        serialized_rows = self.serialize_list(rows)
        return [
            DashboardDailyDataRowResponse(
                id=str(item["id"]),
                restaurant_name=restaurant_lookup.get(str(item.get("tenant_id")), "Unknown restaurant"),
                business_date=str(item.get("business_date") or ""),
                total_revenue=float(item.get("total_revenue", 0.0) or 0.0),
                total_expenses=float(item.get("total_expenses", 0.0) or 0.0),
                total_covers=int(item.get("total_covers", 0) or 0),
            )
            for item in serialized_rows
        ]

    async def _get_recent_cash_rows(self, restaurant_lookup: dict[str, str]) -> list[DashboardCashRowResponse]:
        rows = await self.cash_repository.collection.find(
            {},
            {
                "_id": 1,
                "tenant_id": 1,
                "deposit_date": 1,
                "amount": 1,
                "bank_account": 1,
                "reference": 1,
                "created_at": 1,
            },
        ).sort([("deposit_date", -1), ("created_at", -1)]).limit(6).to_list(length=6)
        serialized_rows = self.serialize_list(rows)
        return [
            DashboardCashRowResponse(
                id=str(item["id"]),
                restaurant_name=restaurant_lookup.get(str(item.get("tenant_id")), "Unknown restaurant"),
                deposit_date=str(item.get("deposit_date") or ""),
                amount=float(item.get("amount", 0.0) or 0.0),
                bank_account=str(item.get("bank_account") or "") or None,
                reference=str(item.get("reference") or "") or None,
            )
            for item in serialized_rows
        ]

    async def _get_recent_inventory_rows(self, restaurant_lookup: dict[str, str]) -> list[DashboardInventoryRowResponse]:
        rows = await self.inventory_repository.collection.find(
            {},
            {
                "_id": 1,
                "tenant_id": 1,
                "product_name": 1,
                "category": 1,
                "stock_quantity": 1,
                "unit_type": 1,
                "stock_status": 1,
                "updated_at": 1,
                "created_at": 1,
            },
        ).sort([("updated_at", -1), ("created_at", -1)]).limit(6).to_list(length=6)
        serialized_rows = self.serialize_list(rows)
        return [
            DashboardInventoryRowResponse(
                id=str(item["id"]),
                restaurant_name=restaurant_lookup.get(str(item.get("tenant_id")), "Unknown restaurant"),
                product_name=str(item.get("product_name") or ""),
                category=str(item.get("category") or ""),
                stock_quantity=float(item.get("stock_quantity", 0.0) or 0.0),
                unit_type=str(item.get("unit_type") or ""),
                stock_status=str(item.get("stock_status") or "") or None,
            )
            for item in serialized_rows
        ]

    @staticmethod
    def _build_monthly_points(counts: list[int]) -> list[DashboardMonthlyPointResponse]:
        return [
            DashboardMonthlyPointResponse(month=index + 1, label=MONTH_LABELS[index], value=value)
            for index, value in enumerate(counts)
        ]

    @staticmethod
    def _build_role_breakdown(role_counts: dict[str, int]) -> list[DashboardRoleBreakdownResponse]:
        return [
            DashboardRoleBreakdownResponse(
                role=role,
                label=ROLE_LABELS[role],
                value=role_counts.get(role, 0),
            )
            for role in (UserRole.SUPER_ADMIN, UserRole.RESTAURANT_OWNER, UserRole.MANAGER, UserRole.STAFF)
        ]

    @staticmethod
    def _build_subscription_breakdown(
        active_subscriptions: int,
        trial_users: int,
    ) -> list[DashboardUserGrowthSliceResponse]:
        total = max(active_subscriptions + trial_users, 1)
        return [
            DashboardUserGrowthSliceResponse(
                label="Active Subscriptions",
                value=active_subscriptions,
                percentage=round((active_subscriptions / total) * 100, 2),
                color_key="navy",
            ),
            DashboardUserGrowthSliceResponse(
                label="Trial Users",
                value=trial_users,
                percentage=round((trial_users / total) * 100, 2),
                color_key="lavender",
            ),
        ]

    @staticmethod
    def _build_monthly_revenue_points(
        users: list[dict],
        plan_map: dict[str, dict],
        year: int,
    ) -> list[DashboardSeriesPointResponse]:
        totals: dict[int, float] = defaultdict(float)
        for month in range(1, 13):
            month_start = datetime(year, month, 1, tzinfo=UTC)
            next_month = datetime(year + (month // 12), ((month % 12) + 1), 1, tzinfo=UTC)
            for user in users:
                if not DashboardService._subscription_overlaps_period(user, month_start, next_month):
                    continue
                totals[month] += DashboardService._monthly_revenue_value(user, plan_map)

        return [
            DashboardSeriesPointResponse(
                key=f"{year}-{index + 1:02d}",
                label=MONTH_LABELS[index].upper(),
                value=round(totals.get(index + 1, 0.0), 2),
            )
            for index in range(12)
        ]

    @staticmethod
    def _build_weekly_revenue_points(
        users: list[dict],
        plan_map: dict[str, dict],
        year: int,
    ) -> list[DashboardSeriesPointResponse]:
        current_date = datetime.now(UTC)
        if year == current_date.year:
            anchor = current_date
        else:
            anchor = datetime(year, 12, 31, tzinfo=UTC)

        week_start = anchor - timedelta(days=anchor.weekday())
        week_starts = [week_start - timedelta(weeks=offset) for offset in range(7, -1, -1)]
        week_ranges = [(start, start + timedelta(days=7)) for start in week_starts]
        return [
            DashboardSeriesPointResponse(
                key=f"{start.isocalendar().year}-W{start.isocalendar().week:02d}",
                label=f"W{start.isocalendar().week:02d}",
                value=round(
                    sum(
                        DashboardService._monthly_revenue_value(user, plan_map)
                        for user in users
                        if DashboardService._subscription_overlaps_period(user, start, end)
                    ),
                    2,
                ),
            )
            for start, _ in week_ranges
            for end in [start + timedelta(days=7)]
        ]

    @staticmethod
    def _subscription_overlaps_period(user: dict, period_start: datetime, period_end: datetime) -> bool:
        if user.get("subscription_status") != SubscriptionStatus.ACTIVE:
            return False

        started_at = DashboardService._as_utc(user.get("subscription_started_at") or user.get("created_at"))
        if not started_at:
            return False

        expires_at = DashboardService._as_utc(user.get("subscription_expires_at"))
        if expires_at is None:
            expires_at = datetime(period_end.year, 12, 31, 23, 59, 59, tzinfo=UTC)

        return started_at < period_end and expires_at >= period_start

    @staticmethod
    def _is_subscription_active_on(user: dict, point_in_time: datetime) -> bool:
        if user.get("subscription_status") != SubscriptionStatus.ACTIVE:
            return False

        started_at = DashboardService._as_utc(user.get("subscription_started_at") or user.get("created_at"))
        if not started_at or started_at > point_in_time:
            return False

        expires_at = DashboardService._as_utc(user.get("subscription_expires_at"))
        return expires_at is None or expires_at >= point_in_time

    @staticmethod
    def _as_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _safe_percent(numerator: float, denominator: float) -> float:
        if denominator <= 0:
            return 0.0
        return round((numerator / denominator) * 100, 2)

    @staticmethod
    def _change_percent(current: float, previous: float) -> float:
        if previous <= 0:
            return round(100.0 if current > 0 else 0.0, 2)
        return round(((current - previous) / previous) * 100, 2)

    @staticmethod
    def _range_start(anchor: datetime, range_key: str) -> datetime:
        days = {"7d": 7, "30d": 30, "90d": 90}.get(range_key, 30)
        normalized = anchor.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        return normalized - timedelta(days=days - 1)

    @staticmethod
    def _bucket_count(range_key: str) -> int:
        return {"7d": 7, "30d": 6, "90d": 3}.get(range_key, 6)

    @staticmethod
    def _bucket_span_days(range_key: str) -> int:
        return {"7d": 1, "30d": 5, "90d": 30}.get(range_key, 5)

    def _build_analytics_user_growth(
        self,
        users: list[dict],
        *,
        range_key: str,
        now: datetime,
    ) -> list[DashboardAnalyticsPointResponse]:
        start = self._range_start(now, range_key)
        bucket_count = self._bucket_count(range_key)
        span_days = self._bucket_span_days(range_key)
        points: list[DashboardAnalyticsPointResponse] = []

        for index in range(bucket_count):
            bucket_start = start + timedelta(days=index * span_days)
            bucket_end = min(bucket_start + timedelta(days=span_days), now + timedelta(days=1))
            value = sum(
                1
                for user in users
                if bucket_start <= (self._as_utc(user.get("created_at")) or now) < bucket_end
            )
            points.append(
                DashboardAnalyticsPointResponse(
                    key=bucket_start.date().isoformat(),
                    label=self._format_analytics_bucket_label(bucket_start, range_key=range_key),
                    value=float(value),
                )
            )

        return points

    def _build_analytics_revenue_growth(
        self,
        users: list[dict],
        *,
        plan_map: dict[str, dict],
        range_key: str,
        now: datetime,
    ) -> list[DashboardAnalyticsPointResponse]:
        start = self._range_start(now, range_key)
        bucket_count = self._bucket_count(range_key)
        span_days = self._bucket_span_days(range_key)
        points: list[DashboardAnalyticsPointResponse] = []

        for index in range(bucket_count):
            bucket_start = start + timedelta(days=index * span_days)
            bucket_end = min(bucket_start + timedelta(days=span_days), now + timedelta(days=1))
            value = round(
                sum(
                    self._monthly_revenue_value(user, plan_map)
                    for user in users
                    if self._subscription_overlaps_period(user, bucket_start, bucket_end)
                ),
                2,
            )
            points.append(
                DashboardAnalyticsPointResponse(
                    key=bucket_start.date().isoformat(),
                    label=self._format_analytics_bucket_label(bucket_start, range_key=range_key),
                    value=value,
                )
            )

        return points

    def _build_analytics_subscription_status(self, users: list[dict]) -> list[DashboardAnalyticsBreakdownItemResponse]:
        active = sum(1 for user in users if user.get("subscription_status") == SubscriptionStatus.ACTIVE)
        trial = sum(1 for user in users if user.get("subscription_status") == SubscriptionStatus.TRIAL)
        other = max(len(users) - active - trial, 0)
        total = max(active + trial + other, 1)
        return [
            DashboardAnalyticsBreakdownItemResponse(
                key="active",
                label="Active",
                value=active,
                percentage=round((active / total) * 100, 2),
                color_key="primary",
            ),
            DashboardAnalyticsBreakdownItemResponse(
                key="trial",
                label="Trial",
                value=trial,
                percentage=round((trial / total) * 100, 2),
                color_key="dark",
            ),
            DashboardAnalyticsBreakdownItemResponse(
                key="other",
                label="Other",
                value=other,
                percentage=round((other / total) * 100, 2),
                color_key="muted",
            ),
        ]

    def _build_analytics_billing_cycle(self, users: list[dict]) -> list[DashboardAnalyticsBreakdownItemResponse]:
        monthly = sum(
            1
            for user in users
            if user.get("subscription_status") == SubscriptionStatus.ACTIVE
            and user.get("subscription_plan") != SubscriptionPlan.ONE_YEAR
        )
        yearly = sum(
            1
            for user in users
            if user.get("subscription_status") == SubscriptionStatus.ACTIVE
            and user.get("subscription_plan") == SubscriptionPlan.ONE_YEAR
        )
        total = max(monthly + yearly, 1)
        return [
            DashboardAnalyticsBreakdownItemResponse(
                key="monthly",
                label="Monthly",
                value=monthly,
                percentage=round((monthly / total) * 100, 2),
                color_key="primary",
            ),
            DashboardAnalyticsBreakdownItemResponse(
                key="yearly",
                label="Yearly",
                value=yearly,
                percentage=round((yearly / total) * 100, 2),
                color_key="dark",
            ),
        ]

    @staticmethod
    def _format_analytics_bucket_label(bucket_start: datetime, *, range_key: str) -> str:
        if range_key == "7d":
            return bucket_start.strftime("%a").upper()
        if range_key == "30d":
            return bucket_start.strftime("%d %b")
        return bucket_start.strftime("%b")

    async def _get_plan_map(self) -> dict[str, dict]:
        plans = await self.subscription_plan_repository.get_active_plans()
        plan_map = {str(plan["name"]): plan for plan in plans}
        if plan_map:
            return plan_map

        settings = get_settings()
        return {
            settings.subscription_plan_name: {
                "name": settings.subscription_plan_name,
                "monthly_price": settings.subscription_plan_monthly_price,
                "annual_price": settings.subscription_plan_annual_price,
                "trial_days": settings.subscription_plan_trial_days,
                "is_active": True,
                "is_visible": settings.subscription_plan_is_visible,
                "is_best_plan": settings.subscription_plan_is_best,
            }
        }

    @staticmethod
    def _monthly_revenue_value(user: dict, plan_map: dict[str, dict]) -> float:
        plan = plan_map.get(user.get("subscription_plan_name"))
        if not plan and len(plan_map) == 1:
            plan = next(iter(plan_map.values()))
        if plan:
            if user.get("subscription_plan") == SubscriptionPlan.ONE_YEAR:
                return round(float(plan["annual_price"]) / 12, 2)
            return round(float(plan["monthly_price"]), 2)

        if user.get("subscription_plan") == SubscriptionPlan.ONE_YEAR:
            return round(300.0 / 12, 2)
        return 30.0

    @staticmethod
    def _format_currency(value: float) -> str:
        return f"€{value:,.2f}" if value >= 0 else f"-€{abs(value):,.2f}"

    @staticmethod
    def _charge_value(user: dict, plan_map: dict[str, dict]) -> float:
        plan = plan_map.get(user.get("subscription_plan_name"))
        if not plan and len(plan_map) == 1:
            plan = next(iter(plan_map.values()))
        if plan:
            if user.get("subscription_plan") == SubscriptionPlan.ONE_YEAR:
                return round(float(plan["annual_price"]), 2)
            return round(float(plan["monthly_price"]), 2)

        if user.get("subscription_plan") == SubscriptionPlan.ONE_YEAR:
            return 300.0
        return 30.0
