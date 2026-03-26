from __future__ import annotations

from fastapi import Depends, Query

from app.config.settings import get_settings
from app.db.mongodb import get_database
from app.repositories.admin_settings import AdminSettingsRepository
from app.repositories.auth_code import AuthCodeRepository
from app.repositories.coupon import CouponRepository
from app.repositories.restaurant_ops import (
    RestaurantCashDepositRepository,
    RestaurantChatRepository,
    RestaurantDailyRecordRepository,
    RestaurantRecordRepository,
    RestaurantWeeklyRecordRepository,
    RestaurantMonthlyRecordRepository,
    RestaurantDocumentRepository,
    RestaurantExpenseRepository,
    RestaurantInsightRepository,
    RestaurantInventoryRepository,
)
from app.repositories.onboarding_profile import OnboardingProfileRepository
from app.repositories.subscription_plan import SubscriptionPlanRepository
from app.repositories.support_ticket import SupportTicketRepository
from app.repositories.user import UserRepository
from app.repositories.user_subscription import UserSubscriptionRepository
from app.services.admin_settings import AdminSettingsService
from app.services.auth import AuthService
from app.services.dashboard import DashboardService
from app.services.email import EmailService
from app.services.restaurant import RestaurantOperationsService
from app.services.onboarding import OnboardingService
from app.services.openai_ops import OpenAIOperationsService
from app.services.subscription import SubscriptionService
from app.services.stripe_billing import StripeBillingService
from app.services.support import SupportService
from app.services.user_management import UserManagementService


async def get_auth_service(db=Depends(get_database)) -> AuthService:
    return AuthService(UserRepository(db), AuthCodeRepository(db), EmailService(get_settings()), SubscriptionPlanRepository(db), UserSubscriptionRepository(db))


async def get_onboarding_service(db=Depends(get_database)) -> OnboardingService:
    return OnboardingService(OnboardingProfileRepository(db), UserRepository(db))


async def get_dashboard_service(db=Depends(get_database)) -> DashboardService:
    return DashboardService(UserRepository(db), OnboardingProfileRepository(db), AuthCodeRepository(db))


async def get_user_management_service(db=Depends(get_database)) -> UserManagementService:
    return UserManagementService(UserRepository(db), OnboardingProfileRepository(db), AuthCodeRepository(db))


async def get_subscription_service(db=Depends(get_database)) -> SubscriptionService:
    return SubscriptionService(UserRepository(db), SubscriptionPlanRepository(db), CouponRepository(db), UserSubscriptionRepository(db), StripeBillingService(get_settings()))


async def get_support_service(db=Depends(get_database)) -> SupportService:
    return SupportService(SupportTicketRepository(db))


async def get_admin_settings_service(db=Depends(get_database)) -> AdminSettingsService:
    return AdminSettingsService(AdminSettingsRepository(db))


def build_restaurant_operations_service(db) -> RestaurantOperationsService:
    return RestaurantOperationsService(
        UserRepository(db),
        RestaurantDocumentRepository(db),
        RestaurantExpenseRepository(db),
        RestaurantCashDepositRepository(db),
        RestaurantDailyRecordRepository(db),
        RestaurantRecordRepository(db),
        RestaurantWeeklyRecordRepository(db),
        RestaurantMonthlyRecordRepository(db),
        RestaurantInventoryRepository(db),
        RestaurantChatRepository(db),
        RestaurantInsightRepository(db),
        OpenAIOperationsService(),
    )


async def get_restaurant_operations_service(db=Depends(get_database)) -> RestaurantOperationsService:
    return build_restaurant_operations_service(db)

