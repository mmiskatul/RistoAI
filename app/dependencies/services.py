from __future__ import annotations

from fastapi import Depends

from app.config.settings import get_settings
from app.db.mongodb import get_database
from app.repositories.auth_code import AuthCodeRepository
from app.repositories.user import UserRepository
from app.services.auth import AuthService
from app.services.email import EmailService


async def get_auth_service(db=Depends(get_database)) -> AuthService:
    return AuthService(UserRepository(db), AuthCodeRepository(db), EmailService(get_settings()))
