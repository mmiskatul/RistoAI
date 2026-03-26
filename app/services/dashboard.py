from __future__ import annotations

from datetime import UTC, datetime

from app.core.enums import SubscriptionStatus, UserRole
from app.repositories.auth_code import AuthCodeRepository
from app.repositories.onboarding_profile import OnboardingProfileRepository
from app.repositories.user import UserRepository
from app.schemas.dashboard import (
    DashboardChartsResponse,
    DashboardHeaderActionResponse,
    DashboardHeaderProfileResponse,
    DashboardHeaderResponse,
    DashboardKpiResponse,
    DashboardMetaResponse,
    DashboardMonthlyPointResponse,
    DashboardOverviewResponse,
    DashboardRevenueGrowthResponse,
    DashboardRoleBreakdownResponse,
    DashboardSidebarFooterActionResponse,
    DashboardSidebarItemResponse,
    DashboardTopCardResponse,
    DashboardUserGrowthResponse,
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

        header_actions = [
            DashboardHeaderActionResponse(key="notifications", label="Notifications"),
            DashboardHeaderActionResponse(key="profile", label="Profile"),
        ]

        return DashboardOverviewResponse(
            header=DashboardHeaderResponse(
                title="Admin Dashboard",
                subtitle="Platform Overview",
                notification_count=pending_verifications,
                actions=header_actions,
                profile=DashboardHeaderProfileResponse(
                    full_name=current_user.get("full_name", "Admin User"),
                    avatar_url=current_user.get("profile_image_url"),
                ),
            ),
            sidebar_items=self._build_sidebar_items(),
            sidebar_footer_action=DashboardSidebarFooterActionResponse(
                label="Logout",
                icon_key="logout",
                endpoint="/api/v1/auth/admin/login",
            ),
            header_actions=header_actions,
            top_cards=[
                DashboardTopCardResponse(
                    key="total_users",
                    label="Total Users",
                    value=summary.total_users,
                    value_formatted=self._format_compact_number(summary.total_users),
                    change_percent=12.4,
                    change_label="+12.4%",
                    trend="up",
                    icon_key="users",
                ),
                DashboardTopCardResponse(
                    key="active_subscriptions",
                    label="Active Subscriptions",
                    value=active_subscriptions,
                    value_formatted=self._format_compact_number(active_subscriptions),
                    change_percent=5.2,
                    change_label="+5.2%",
                    trend="up",
                    icon_key="subscriptions",
                ),
                DashboardTopCardResponse(
                    key="monthly_revenue",
                    label="Monthly Revenue",
                    value=monthly_revenue,
                    value_formatted=self._format_currency(monthly_revenue),
                    change_percent=18.2,
                    change_label="+18.2%",
                    trend="up",
                    icon_key="revenue",
                ),
                DashboardTopCardResponse(
                    key="trial_users",
                    label="Trial Users",
                    value=trial_users,
                    value_formatted=self._format_compact_number(trial_users),
                    change_percent=-2.1,
                    change_label="-2.1%",
                    trend="down",
                    icon_key="trial",
                ),
            ],
            revenue_growth=DashboardRevenueGrowthResponse(
                selected_year=selected_year,
                year_options=[selected_year - 1, selected_year],
                points=[
                    DashboardMonthlyPointResponse(month=point.month, label=point.label.upper(), value=self._estimate_monthly_revenue_from_count(float(point.value)))
                    for point in charts.monthly_new_users
                ],
            ),
            user_growth=self._build_user_growth(active_subscriptions=active_subscriptions, trial_users=trial_users),
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
    def _build_sidebar_items() -> list[DashboardSidebarItemResponse]:
        return [
            DashboardSidebarItemResponse(key="dashboard", label="Dashboard", icon_key="dashboard", endpoint="/api/v1/dashboard/overview", active=True),
            DashboardSidebarItemResponse(key="users", label="Users Management", icon_key="users", endpoint="/api/v1/users"),
            DashboardSidebarItemResponse(key="subscriptions", label="Subscriptions", icon_key="subscriptions", endpoint="/api/v1/subscriptions/plans"),
            DashboardSidebarItemResponse(key="analytics", label="Analytics", icon_key="analytics", endpoint="/api/v1/dashboard/overview"),
            DashboardSidebarItemResponse(key="support", label="Support", icon_key="support", endpoint="/api/v1/support/management"),
            DashboardSidebarItemResponse(key="settings", label="Settings", icon_key="settings", endpoint="/api/v1/auth/me"),
        ]

    def _build_user_growth(self, *, active_subscriptions: int, trial_users: int) -> DashboardUserGrowthResponse:
        total = active_subscriptions + trial_users
        active_percentage = round((active_subscriptions / total) * 100, 1) if total else 0.0
        trial_percentage = round((trial_users / total) * 100, 1) if total else 0.0
        return DashboardUserGrowthResponse(
            total_value=total,
            total_value_formatted=self._format_compact_number(total),
            slices=[
                DashboardUserGrowthSliceResponse(label="Active Subscriptions", value=active_subscriptions, percentage=active_percentage, color_key="active"),
                DashboardUserGrowthSliceResponse(label="Trial Users", value=trial_users, percentage=trial_percentage, color_key="trial"),
            ],
        )

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
    def _estimate_monthly_revenue_from_count(count: float) -> float:
        return round(count * 29.0, 2)

    @staticmethod
    def _format_currency(value: float) -> str:
        return f"${value:,.2f}"

    @staticmethod
    def _format_compact_number(value: int | float) -> str:
        number = float(value)
        if number >= 1_000_000:
            return f"{number / 1_000_000:.1f}M"
        if number >= 1_000:
            return f"{number / 1_000:.1f}k"
        if number.is_integer():
            return str(int(number))
        return f"{number:.1f}"
