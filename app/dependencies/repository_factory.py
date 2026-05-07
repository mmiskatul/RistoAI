from __future__ import annotations

from app.repositories.admin_settings import AdminSettingsRepository
from app.repositories.auth_code import AuthCodeRepository
from app.repositories.coupon import CouponRepository
from app.repositories.onboarding_profile import OnboardingProfileRepository
from app.repositories.restaurant_ops import (
    RestaurantBankAccountRepository,
    RestaurantCashDepositRepository,
    RestaurantChatMemoryRepository,
    RestaurantChatRepository,
    RestaurantDailyRecordRepository,
    RestaurantDocumentRepository,
    RestaurantExpenseRepository,
    RestaurantFinanceTransactionRepository,
    RestaurantInsightRepository,
    RestaurantInventoryCategoryRepository,
    RestaurantInventoryRepository,
    RestaurantInventorySupplierRepository,
    RestaurantMonthlyRecordRepository,
    RestaurantRecordRepository,
    RestaurantWeeklyRecordRepository,
)
from app.repositories.subscription_plan import SubscriptionPlanRepository
from app.repositories.support_ticket import SupportTicketRepository
from app.repositories.user import UserRepository
from app.repositories.user_subscription import UserSubscriptionRepository


class RepositoryFactory:
    def __init__(self, db) -> None:
        self.db = db

    def admin_settings(self) -> AdminSettingsRepository:
        return AdminSettingsRepository(self.db)

    def auth_codes(self) -> AuthCodeRepository:
        return AuthCodeRepository(self.db)

    def coupons(self) -> CouponRepository:
        return CouponRepository(self.db)

    def onboarding_profiles(self) -> OnboardingProfileRepository:
        return OnboardingProfileRepository(self.db)

    def subscription_plans(self) -> SubscriptionPlanRepository:
        return SubscriptionPlanRepository(self.db)

    def support_tickets(self) -> SupportTicketRepository:
        return SupportTicketRepository(self.db)

    def users(self) -> UserRepository:
        return UserRepository(self.db)

    def user_subscriptions(self) -> UserSubscriptionRepository:
        return UserSubscriptionRepository(self.db)

    def restaurant_bank_accounts(self) -> RestaurantBankAccountRepository:
        return RestaurantBankAccountRepository(self.db)

    def restaurant_cash_deposits(self) -> RestaurantCashDepositRepository:
        return RestaurantCashDepositRepository(self.db)

    def restaurant_chats(self) -> RestaurantChatRepository:
        return RestaurantChatRepository(self.db)

    def restaurant_chat_memories(self) -> RestaurantChatMemoryRepository:
        return RestaurantChatMemoryRepository(self.db)

    def restaurant_daily_records(self) -> RestaurantDailyRecordRepository:
        return RestaurantDailyRecordRepository(self.db)

    def restaurant_documents(self) -> RestaurantDocumentRepository:
        return RestaurantDocumentRepository(self.db)

    def restaurant_expenses(self) -> RestaurantExpenseRepository:
        return RestaurantExpenseRepository(self.db)

    def restaurant_finance_transactions(self) -> RestaurantFinanceTransactionRepository:
        return RestaurantFinanceTransactionRepository(self.db)

    def restaurant_insights(self) -> RestaurantInsightRepository:
        return RestaurantInsightRepository(self.db)

    def restaurant_inventory(self) -> RestaurantInventoryRepository:
        return RestaurantInventoryRepository(self.db)

    def restaurant_inventory_categories(self) -> RestaurantInventoryCategoryRepository:
        return RestaurantInventoryCategoryRepository(self.db)

    def restaurant_inventory_suppliers(self) -> RestaurantInventorySupplierRepository:
        return RestaurantInventorySupplierRepository(self.db)

    def restaurant_monthly_records(self) -> RestaurantMonthlyRecordRepository:
        return RestaurantMonthlyRecordRepository(self.db)

    def restaurant_records(self) -> RestaurantRecordRepository:
        return RestaurantRecordRepository(self.db)

    def restaurant_weekly_records(self) -> RestaurantWeeklyRecordRepository:
        return RestaurantWeeklyRecordRepository(self.db)
