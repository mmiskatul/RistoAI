from __future__ import annotations

from app.core.enums import UserRole
from app.core.exceptions import AuthorizationException, ConflictException, AuthenticationException
from app.core.security import password_manager, token_manager
from app.repositories.user import UserRepository
from app.schemas.auth import AuthResponse, AuthUserResponse, LoginRequest, RefreshTokenRequest, RegisterRequest, TokenResponse
from app.services.base import BaseService


class AuthService(BaseService):
    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    async def register(self, payload: RegisterRequest) -> AuthResponse:
        if await self.user_repository.get_by_email(payload.email):
            raise ConflictException("An account with this email already exists")
        user = await self.user_repository.create(
            {
                "email": payload.email.lower(),
                "full_name": payload.full_name,
                "phone": payload.phone,
                "hashed_password": password_manager.hash_password(payload.password),
                "role": UserRole.RESTAURANT_OWNER,
                "is_active": True,
                "restaurant_ids": [],
                "branch_ids": [],
            }
        )
        return self._build_auth_response(user)

    async def login(self, payload: LoginRequest) -> AuthResponse:
        user = await self.user_repository.get_by_email(payload.email)
        if not user or not password_manager.verify_password(payload.password, user["hashed_password"]):
            raise AuthenticationException("Invalid credentials")
        if not user["is_active"]:
            raise AuthenticationException("User account is inactive")
        return self._build_auth_response(user)

    async def refresh(self, payload: RefreshTokenRequest) -> TokenResponse:
        token_payload = token_manager.decode_token(payload.refresh_token)
        if token_payload.get("type") != "refresh":
            raise AuthenticationException("Invalid refresh token")
        user = await self.user_repository.get_optional_by_id(token_payload["sub"])
        if not user:
            raise AuthenticationException("User not found")
        return self._build_tokens(str(user["_id"]), str(user["role"]))

    async def get_me(self, current_user: dict) -> AuthUserResponse:
        return AuthUserResponse(**self.serialize(current_user))

    def _build_auth_response(self, user: dict) -> AuthResponse:
        serialized = self.serialize(user)
        return AuthResponse(user=AuthUserResponse(**serialized), tokens=self._build_tokens(serialized["id"], serialized["role"]))

    @staticmethod
    def _build_tokens(user_id: str, role: str) -> TokenResponse:
        return TokenResponse(
            access_token=token_manager.create_access_token(subject=user_id, role=role),
            refresh_token=token_manager.create_refresh_token(subject=user_id, role=role),
        )
