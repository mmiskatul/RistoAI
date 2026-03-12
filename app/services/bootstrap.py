from __future__ import annotations

from app.config.settings import Settings
from app.core.enums import AppLanguage, UserRole
from app.core.security import password_manager
from app.repositories.user import UserRepository


class BootstrapService:
    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

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

        updates = {
            key: value
            for key, value in payload.items()
            if existing_user.get(key) != value
        }
        if not password_manager.verify_password(settings.super_admin_password, existing_user['hashed_password']):
            updates['hashed_password'] = password_manager.hash_password(settings.super_admin_password)

        if updates:
            await self.user_repository.update(existing_user['_id'], updates)
