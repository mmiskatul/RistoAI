from __future__ import annotations

from fastapi import Depends

from app.config.settings import get_settings
from app.db.mongodb import get_database
from app.dependencies.repository_factory import RepositoryFactory
from app.services.admin_settings import AdminSettingsService
from app.services.auth import AuthService
from app.services.dashboard import DashboardService
from app.services.email import EmailService
from app.services.image_storage import ImageStorageService, build_image_storage_service
from app.services.restaurant import RestaurantOperationsService
from app.services.onboarding import OnboardingService
from app.services.openai_ops import OpenAIOperationsService
from app.services.subscription import SubscriptionService
from app.services.stripe_billing import StripeBillingService
from app.services.support import SupportService
from app.services.user_management import UserManagementService


async def get_auth_service(db=Depends(get_database)) -> AuthService:
    repos = RepositoryFactory(db)
    return AuthService(
        repos.users(),
        repos.auth_codes(),
        EmailService(get_settings()),
        repos.onboarding_profiles(),
    )


async def get_onboarding_service(db=Depends(get_database)) -> OnboardingService:
    settings = get_settings()
    repos = RepositoryFactory(db)
    return OnboardingService(repos.onboarding_profiles(), repos.users(), build_image_storage_service(settings))


async def get_dashboard_service(db=Depends(get_database)) -> DashboardService:
    repos = RepositoryFactory(db)
    return DashboardService(
        repos.users(),
        repos.onboarding_profiles(),
        repos.auth_codes(),
        repos.subscription_plans(),
        repos.restaurant_records(),
        repos.restaurant_cash_deposits(),
        repos.restaurant_inventory(),
    )


async def get_user_management_service(db=Depends(get_database)) -> UserManagementService:
    repos = RepositoryFactory(db)
    return UserManagementService(repos.users(), repos.onboarding_profiles(), repos.auth_codes())


async def get_subscription_service(db=Depends(get_database)) -> SubscriptionService:
    repos = RepositoryFactory(db)
    return SubscriptionService(
        repos.users(),
        repos.subscription_plans(),
        repos.coupons(),
        repos.user_subscriptions(),
        StripeBillingService(get_settings()),
    )


async def get_support_service(db=Depends(get_database)) -> SupportService:
    return SupportService(RepositoryFactory(db).support_tickets())


async def get_admin_settings_service(db=Depends(get_database)) -> AdminSettingsService:
    settings = get_settings()
    repos = RepositoryFactory(db)
    return AdminSettingsService(
        repos.admin_settings(),
        repos.users(),
        build_image_storage_service(settings),
    )


def build_restaurant_operations_service(db) -> RestaurantOperationsService:
    settings = get_settings()
    repos = RepositoryFactory(db)
    return RestaurantOperationsService(
        repos.users(),
        repos.restaurant_documents(),
        repos.restaurant_expenses(),
        repos.restaurant_food_costs(),
        repos.restaurant_cash_deposits(),
        repos.restaurant_bank_accounts(),
        repos.restaurant_daily_records(),
        repos.restaurant_records(),
        repos.restaurant_weekly_records(),
        repos.restaurant_monthly_records(),
        repos.restaurant_finance_transactions(),
        repos.restaurant_inventory(),
        repos.restaurant_inventory_categories(),
        repos.restaurant_inventory_suppliers(),
        repos.restaurant_chats(),
        repos.restaurant_insights(),
        repos.restaurant_notifications(),
        OpenAIOperationsService(),
        repos.restaurant_chat_memories(),
        repos.onboarding_profiles(),
        build_image_storage_service(settings),
    )


async def get_restaurant_operations_service(db=Depends(get_database)) -> RestaurantOperationsService:
    return build_restaurant_operations_service(db)


async def get_image_storage_service() -> ImageStorageService:
    settings = get_settings()
    return build_image_storage_service(settings)
