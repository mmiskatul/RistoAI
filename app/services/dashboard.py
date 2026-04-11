from __future__ import annotations

from datetime import UTC, datetime

from app.core.enums import SubscriptionStatus, UserRole
from app.repositories.auth_code import AuthCodeRepository
from app.repositories.onboarding_profile import OnboardingProfileRepository
from app.repositories.user import UserRepository
from app.schemas.dashboard import (
    DashboardChartsResponse,
    DashboardKpiResponse,
    DashboardMetaResponse,
    DashboardMonthlyPointResponse,
    DashboardOverviewResponse,
    DashboardRoleBreakdownResponse,
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
    ) -> None:
        self.user_repository = user_repository
        self.onboarding_repository = onboarding_repository
        self.auth_code_repository = auth_code_repository

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
        role_counts = await self.user_repository.get_role_counts()
        total_users = await self.user_repository.count()
        active_users = await self.user_repository.count({"is_active": True})
        verified_users = await self.user_repository.count({"email_verified": True})
        completed_onboarding = await self.onboarding_repository.count_completed()
        pending_verifications = await self.auth_code_repository.count_pending(purpose="restaurant_registration")
        monthly_new_users = await self.user_repository.get_monthly_registrations(selected_year)
        monthly_completed_onboarding = await self.onboarding_repository.get_monthly_completed_counts(selected_year)
        subscription_users = await self.user_repository.get_users_with_subscription_data()

        active_subscriptions = sum(1 for user in subscription_users if user.get("subscription_status") == SubscriptionStatus.ACTIVE)
        trial_users = sum(1 for user in subscription_users if user.get("subscription_status") == SubscriptionStatus.TRIAL)
        monthly_revenue = round(sum(self._estimate_monthly_revenue(user) for user in subscription_users), 2)

        summary = DashboardKpiResponse(
            total_users=total_users,
            active_users=active_users,
            verified_users=verified_users,
            completed_onboarding=completed_onboarding,
            pending_verifications=pending_verifications,
            admins=role_counts.get(UserRole.SUPER_ADMIN, 0),
            restaurant_owners=role_counts.get(UserRole.RESTAURANT_OWNER, 0),
            managers=role_counts.get(UserRole.MANAGER, 0),
            staff=role_counts.get(UserRole.STAFF, 0),
        )
        charts = DashboardChartsResponse(
            monthly_new_users=self._build_monthly_points(monthly_new_users),
            monthly_completed_onboarding=self._build_monthly_points(monthly_completed_onboarding),
            users_by_role=self._build_role_breakdown(role_counts),
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
    def _estimate_monthly_revenue(user: dict) -> float:
        status = user.get("subscription_status")
        if status != SubscriptionStatus.ACTIVE:
            return 0.0
        plan = user.get("subscription_plan")
        if plan == "1_year":
            return round(290.0 / 12, 2)
        return 29.0

    @staticmethod
    def _format_currency(value: float) -> str:
        return f"${value:,.2f}"
