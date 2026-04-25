from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.enums import UserRole
from app.core.exceptions import AuthenticationException, AuthorizationException
from app.core.security import token_manager
from app.db.mongodb import get_database
from app.repositories.user import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db=Depends(get_database),
) -> dict:
    return await _resolve_current_user(credentials, db, allow_inactive=False)


async def get_current_user_allow_inactive(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db=Depends(get_database),
) -> dict:
    return await _resolve_current_user(credentials, db, allow_inactive=True)


async def _resolve_current_user(
    credentials: HTTPAuthorizationCredentials | None,
    db,
    *,
    allow_inactive: bool,
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationException("Missing bearer token")

    token = credentials.credentials
    payload = token_manager.decode_token(token)
    if payload.get("type") != "access":
        raise AuthenticationException("Invalid access token")
    user = await UserRepository(db).get_optional_by_id(payload["sub"])
    if not user:
        raise AuthenticationException("User account is invalid or inactive")
    if not allow_inactive and not user.get("is_active", False):
        raise AuthenticationException("User account is invalid or inactive")
    return user


def require_roles(*roles: UserRole) -> Callable:
    async def role_dependency(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in roles:
            raise AuthorizationException("You do not have permission to access this endpoint")
        return current_user

    return role_dependency


def require_roles_allow_inactive(*roles: UserRole) -> Callable:
    async def role_dependency(current_user: dict = Depends(get_current_user_allow_inactive)) -> dict:
        if current_user["role"] not in roles:
            raise AuthorizationException("You do not have permission to access this endpoint")
        return current_user

    return role_dependency
