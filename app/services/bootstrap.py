from __future__ import annotations

from app.config.settings import Settings
from app.core.enums import AppLanguage, UserRole
from app.core.security import password_manager
from app.repositories.subscription_plan import SubscriptionPlanRepository
from app.repositories.user import UserRepository


class BootstrapService:
    SINGLETON_KEY = 'default_plan'

    def __init__(
        self,
        user_repository: UserRepository,
        subscription_plan_repository: SubscriptionPlanRepository | None = None,
    ) -> None:
        self.user_repository = user_repository
        self.subscription_plan_repository = subscription_plan_repository

    async def ensure_super_admin(self, settings: Settings) -> None:
        if not settings.super_admin_email or not settings.super_admin_password:
            return

        existing_user = await self.user_repository.get_by_email(str(settings.super_admin_email))
        payload = {
            'email': str(settings.super_admin_email).lower(),
            'full_name': settings.super_admin_full_name,
            'role': UserRole.SUPER_ADMIN,
            'preferred_language': AppLanguage.ENGLISH,
            'is_active': True,
            'email_verified': True,
        }

        if not existing_user:
            await self.user_repository.create(
                {
                    **payload,
                    'hashed_password': password_manager.hash_password(settings.super_admin_password),
                }
            )
            return

        updates = {key: value for key, value in payload.items() if existing_user.get(key) != value}
        if not password_manager.verify_password(settings.super_admin_password, existing_user['hashed_password']):
            updates['hashed_password'] = password_manager.hash_password(settings.super_admin_password)

        if updates:
            await self.user_repository.update(existing_user['_id'], updates)

    async def ensure_default_subscription_plan(self, settings: Settings) -> None:
        if self.subscription_plan_repository is None:
            return

        existing_plan = await self.subscription_plan_repository.get_optional_plan()
        if existing_plan:
            updates = {
                'singleton_key': self.SINGLETON_KEY,
                'name': settings.subscription_plan_name,
                'monthly_price': settings.subscription_plan_monthly_price,
                'annual_price': settings.subscription_plan_annual_price,
                'trial_days': settings.subscription_plan_trial_days,
                'features': settings.subscription_plan_features,
                'is_visible': settings.subscription_plan_is_visible,
                'is_active': settings.subscription_plan_is_active,
                'is_best_plan': settings.subscription_plan_is_best,
            }
            await self.subscription_plan_repository.update(existing_plan['_id'], updates)
            return

        await self.subscription_plan_repository.create(
            {
                'singleton_key': self.SINGLETON_KEY,
                'name': settings.subscription_plan_name,
                'monthly_price': settings.subscription_plan_monthly_price,
                'annual_price': settings.subscription_plan_annual_price,
                'trial_days': settings.subscription_plan_trial_days,
                'features': settings.subscription_plan_features,
                'is_visible': settings.subscription_plan_is_visible,
                'is_active': settings.subscription_plan_is_active,
                'is_best_plan': settings.subscription_plan_is_best,
            }
        )
