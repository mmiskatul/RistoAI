from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.core.constants import API_V1_PREFIX
from app.core.enums import UserRole
from app.core.exceptions import AuthenticationException, AuthorizationException
from app.core.security import token_manager
from app.db.mongodb import get_database
from app.repositories.user import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{API_V1_PREFIX}/auth/restaurant/login")


async def get_current_user(token: str = Depends(oauth2_scheme), db=Depends(get_database)) -> dict:
    payload = token_manager.decode_token(token)
    if payload.get("type") != "access":
        raise AuthenticationException("Invalid access token")
    user = await UserRepository(db).get_optional_by_id(payload["sub"])
    if not user or not user.get("is_active", False):
        raise AuthenticationException("User account is invalid or inactive")
    return user


def require_roles(*roles: UserRole) -> Callable:
    async def role_dependency(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in roles:
            raise AuthorizationException("You do not have permission to access this endpoint")
        return current_user

    return role_dependency
