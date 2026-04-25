from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from app.core.enums import SubscriptionPlan, SubscriptionStatus, UserRole
from app.repositories.auth_code import AuthCodeRepository
from app.repositories.onboarding_profile import OnboardingProfileRepository
from app.repositories.subscription_plan import SubscriptionPlanRepository
from app.repositories.user import UserRepository
from app.schemas.dashboard import (
    DashboardChartsResponse,
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
    ) -> None:
        self.user_repository = user_repository
        self.onboarding_repository = onboarding_repository
        self.auth_code_repository = auth_code_repository
        self.subscription_plan_repository = subscription_plan_repository

    async def get_user_metrics(self) -> DashboardUserMetricsResponse:
        role_counts = await self.user_repository.get_role_counts()
        total_users = await self.user_repository.count()
        active_users = await self.user_repository.count({"is_active": True})
        verified_users = await self.user_repository.count({"email_verified": True})

        return DashboardUserMetricsResponse(
            total_users=total_users,
            active_users=active_users,
            verified_users=verified_users,
            admins=role_counts.get(UserRole.SUPER_ADMIN, 0),
            restaurant_owners=role_counts.get(UserRole.RESTAURANT_OWNER, 0),
            managers=role_counts.get(UserRole.MANAGER, 0),
            staff=role_counts.get(UserRole.STAFF, 0),
        )

    async def get_overview(self, current_user: dict, year: int | None = None) -> DashboardOverviewResponse:
        selected_year = year or datetime.now(UTC).year
        del current_user
        role_counts = await self.user_repository.get_role_counts()
        total_users = await self.user_repository.count()
        active_users = await self.user_repository.count({"is_active": True})
        verified_users = await self.user_repository.count({"email_verified": True})
        completed_onboarding = await self.onboarding_repository.count_completed()
        pending_verifications = await self.auth_code_repository.count_pending(purpose="restaurant_registration")
        monthly_new_users = await self.user_repository.get_monthly_registrations(selected_year)
        monthly_completed_onboarding = await self.onboarding_repository.get_monthly_completed_counts(selected_year)
        subscription_users = await self.user_repository.get_users_with_subscription_data()
        plan_map = await self._get_plan_map()

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

        return DashboardOverviewResponse(
            summary=summary,
            charts=charts,
            meta=DashboardMetaResponse(year=selected_year),
        )

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
    def _as_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    async def _get_plan_map(self) -> dict[str, dict]:
        plans = await self.subscription_plan_repository.get_active_plans()
        return {str(plan["name"]): plan for plan in plans}

    @staticmethod
    def _monthly_revenue_value(user: dict, plan_map: dict[str, dict]) -> float:
        plan = plan_map.get(user.get("subscription_plan_name"))
        if plan:
            if user.get("subscription_plan") == SubscriptionPlan.ONE_YEAR:
                return round(float(plan["annual_price"]) / 12, 2)
            return round(float(plan["monthly_price"]), 2)

        if user.get("subscription_plan") == SubscriptionPlan.ONE_YEAR:
            return round(290.0 / 12, 2)
        return 29.0

    @staticmethod
    def _charge_value(user: dict, plan_map: dict[str, dict]) -> float:
        plan = plan_map.get(user.get("subscription_plan_name"))
        if plan:
            if user.get("subscription_plan") == SubscriptionPlan.ONE_YEAR:
                return round(float(plan["annual_price"]), 2)
            return round(float(plan["monthly_price"]), 2)

        if user.get("subscription_plan") == SubscriptionPlan.ONE_YEAR:
            return 290.0
        return 29.0
