from __future__ import annotations

import asyncio

from mongomock_motor import AsyncMongoMockClient

from app.config.settings import Settings
from app.core.enums import AppLanguage, UserRole
from app.core.security import password_manager
from app.repositories.user import UserRepository
from app.services.bootstrap import BootstrapService



def test_ensure_super_admin_creates_admin_user_from_settings():
    mock_db = AsyncMongoMockClient()['ristoai_test']
    settings = Settings(
        SMTP_ENABLED=False,
        SUPER_ADMIN_EMAIL='admin@example.com',
        SUPER_ADMIN_PASSWORD='AdminPass123',
        SUPER_ADMIN_FULL_NAME='Platform Admin',
    )

    asyncio.run(BootstrapService(UserRepository(mock_db)).ensure_super_admin(settings))
    user = asyncio.run(UserRepository(mock_db).get_by_email('admin@example.com'))

    assert user is not None
    assert user['role'] == UserRole.SUPER_ADMIN
    assert user['preferred_language'] == AppLanguage.ENGLISH
    assert user['email_verified'] is True
    assert user['is_active'] is True
    assert user['full_name'] == 'Platform Admin'
    assert password_manager.verify_password('AdminPass123', user['hashed_password']) is True
