from __future__ import annotations

import secrets
from datetime import UTC, datetime

from app.config.settings import get_settings
from app.core.enums import AppLanguage, UserRole
from app.core.exceptions import AuthenticationException, ConflictException, ValidationException
from app.core.security import password_manager, token_manager
from app.repositories.auth_code import AuthCodeRepository
from app.repositories.user import UserRepository
from app.schemas.auth import (
    AuthChallengeResponse,
    AuthResponse,
    AuthUserResponse,
    ForgotPasswordRequest,
    LanguagePreferenceResponse,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UpdateLanguagePreferenceRequest,
    VerifyCodeRequest,
)
from app.schemas.common import MessageResponse
from app.services.base import BaseService
from app.services.email import EmailService


class AuthService(BaseService):
    RESTAURANT_REGISTRATION_PURPOSE = 'restaurant_registration'
    RESTAURANT_PASSWORD_RESET_PURPOSE = 'restaurant_password_reset'
    ADMIN_PASSWORD_RESET_PURPOSE = 'admin_password_reset'
    RESTAURANT_AUTH_ROLES = {UserRole.RESTAURANT_OWNER, UserRole.MANAGER, UserRole.STAFF}
    ADMIN_AUTH_ROLES = {UserRole.SUPER_ADMIN}
    CODE_EXPIRY_SECONDS = 600

    def __init__(
        self,
        user_repository: UserRepository,
        auth_code_repository: AuthCodeRepository,
        email_service: EmailService,
    ) -> None:
        self.user_repository = user_repository
        self.auth_code_repository = auth_code_repository
        self.email_service = email_service
        self.settings = get_settings()

    async def register_restaurant(self, payload: RegisterRequest) -> AuthChallengeResponse:
        user = await self.user_repository.get_by_email(payload.email)
        if user and user.get('email_verified'):
            raise ConflictException('An account with this email already exists')

        if user:
            user = await self.user_repository.update(
                user['_id'],
                {
                    'full_name': payload.full_name,
                    'phone': payload.phone,
                    'hashed_password': password_manager.hash_password(payload.password),
                    'role': UserRole.RESTAURANT_OWNER,
                    'preferred_language': user.get('preferred_language', AppLanguage.ENGLISH),
                    'is_active': True,
                    'email_verified': False,
                    'subscription_plan_name': user.get('subscription_plan_name'),
                    'subscription_plan': user.get('subscription_plan'),
                    'subscription_status': user.get('subscription_status'),
                    'subscription_started_at': user.get('subscription_started_at'),
                    'subscription_expires_at': user.get('subscription_expires_at'),
                },
            )
        else:
            user = await self.user_repository.create(
                {
                    'email': payload.email.lower(),
                    'full_name': payload.full_name,
                    'phone': payload.phone,
                    'hashed_password': password_manager.hash_password(payload.password),
                    'role': UserRole.RESTAURANT_OWNER,
                    'preferred_language': AppLanguage.ENGLISH,
                    'is_active': True,
                    'email_verified': False,
                    'restaurant_name': None,
                    'location': None,
                    'subscription_plan_name': None,
                    'subscription_plan': None,
                    'subscription_status': None,
                    'subscription_started_at': None,
                    'subscription_expires_at': None,
                }
            )

        return await self._issue_challenge(user=user, purpose=self.RESTAURANT_REGISTRATION_PURPOSE)

    async def verify_restaurant_registration(self, payload: VerifyCodeRequest) -> AuthResponse:
        user = await self.user_repository.get_by_email(payload.email)
        if not user:
            raise AuthenticationException('User not found')
        if user['role'] not in self.RESTAURANT_AUTH_ROLES:
            raise AuthenticationException('This account is not a restaurant account')
        await self._verify_code(email=payload.email, code=payload.code, purpose=self.RESTAURANT_REGISTRATION_PURPOSE)
        user = await self.user_repository.update(user['_id'], {'email_verified': True, 'is_active': True})
        return self._build_auth_response(user)

    async def login_restaurant(self, payload: LoginRequest) -> AuthResponse:
        user = await self._authenticate_login(payload)
        if user['role'] not in self.RESTAURANT_AUTH_ROLES:
            raise AuthenticationException('Use the admin login endpoint for this account')
        return self._build_auth_response(user)

    async def login_admin(self, payload: LoginRequest) -> AuthResponse:
        user = await self._authenticate_login(payload)
        if user['role'] not in self.ADMIN_AUTH_ROLES:
            raise AuthenticationException('Use the restaurant login endpoint for this account')
        return self._build_auth_response(user)

    async def forgot_password_restaurant(self, payload: ForgotPasswordRequest) -> AuthChallengeResponse:
        user = await self._get_password_reset_user(payload.email, self.RESTAURANT_AUTH_ROLES, 'This account is not a restaurant account')
        return await self._issue_challenge(user=user, purpose=self.RESTAURANT_PASSWORD_RESET_PURPOSE)

    async def reset_password_restaurant(self, payload: ResetPasswordRequest) -> MessageResponse:
        user = await self._get_password_reset_user(payload.email, self.RESTAURANT_AUTH_ROLES, 'This account is not a restaurant account')
        await self._verify_code(email=payload.email, code=payload.code, purpose=self.RESTAURANT_PASSWORD_RESET_PURPOSE)
        await self.user_repository.update(user['_id'], {'hashed_password': password_manager.hash_password(payload.new_password)})
        return MessageResponse(message='Restaurant account password reset successful')

    async def forgot_password_admin(self, payload: ForgotPasswordRequest) -> AuthChallengeResponse:
        user = await self._get_password_reset_user(payload.email, self.ADMIN_AUTH_ROLES, 'This account is not an admin account')
        return await self._issue_challenge(user=user, purpose=self.ADMIN_PASSWORD_RESET_PURPOSE)

    async def reset_password_admin(self, payload: ResetPasswordRequest) -> MessageResponse:
        user = await self._get_password_reset_user(payload.email, self.ADMIN_AUTH_ROLES, 'This account is not an admin account')
        await self._verify_code(email=payload.email, code=payload.code, purpose=self.ADMIN_PASSWORD_RESET_PURPOSE)
        await self.user_repository.update(user['_id'], {'hashed_password': password_manager.hash_password(payload.new_password)})
        return MessageResponse(message='Admin account password reset successful')

    async def refresh(self, payload: RefreshTokenRequest) -> TokenResponse:
        token_payload = token_manager.decode_token(payload.refresh_token)
        if token_payload.get('type') != 'refresh':
            raise AuthenticationException('Invalid refresh token')
        user = await self.user_repository.get_optional_by_id(token_payload['sub'])
        if not user:
            raise AuthenticationException('User not found')
        return self._build_tokens(str(user['_id']), str(user['role']))

    async def get_me(self, current_user: dict) -> AuthUserResponse:
        return self._to_auth_user_response(current_user)

    async def get_language_preference(self, current_user: dict) -> LanguagePreferenceResponse:
        return LanguagePreferenceResponse(preferred_language=current_user.get('preferred_language', AppLanguage.ENGLISH))

    async def update_language_preference(
        self,
        current_user: dict,
        payload: UpdateLanguagePreferenceRequest,
    ) -> LanguagePreferenceResponse:
        updated_user = await self.user_repository.update(
            current_user['_id'],
            {'preferred_language': payload.preferred_language},
        )
        return LanguagePreferenceResponse(preferred_language=updated_user.get('preferred_language', AppLanguage.ENGLISH))

    async def _authenticate_login(self, payload: LoginRequest) -> dict:
        user = await self.user_repository.get_by_email(payload.email)
        if not user or not password_manager.verify_password(payload.password, user['hashed_password']):
            raise AuthenticationException('Invalid credentials')
        if not user['is_active']:
            raise AuthenticationException('User account is inactive')
        if not user.get('email_verified', False):
            raise AuthenticationException('Email is not verified')
        return user

    async def _get_password_reset_user(self, email: str, allowed_roles: set[UserRole], wrong_role_message: str) -> dict:
        user = await self.user_repository.get_by_email(email)
        if not user:
            raise AuthenticationException('User not found')
        if user['role'] not in allowed_roles:
            raise AuthenticationException(wrong_role_message)
        if not user.get('email_verified', False):
            raise AuthenticationException('Email is not verified')
        return user

    async def _issue_challenge(self, *, user: dict, purpose: str) -> AuthChallengeResponse:
        code = f'{secrets.randbelow(10**6):06d}'
        await self.auth_code_repository.create_code(
            user_id=user['_id'],
            email=user['email'],
            purpose=purpose,
            code=code,
            expires_in_seconds=self.CODE_EXPIRY_SECONDS,
        )
        await self.email_service.send_auth_code(
            email=user['email'],
            full_name=user['full_name'],
            code=code,
            purpose=purpose,
        )
        return AuthChallengeResponse(
            message=f"Verification code sent for {purpose.replace('_', ' ')}",
            purpose=purpose,
            email=user['email'],
            expires_in_seconds=self.CODE_EXPIRY_SECONDS,
            debug_verification_code=code if self.settings.debug else None,
        )

    async def _verify_code(self, *, email: str, code: str, purpose: str) -> None:
        auth_code = await self.auth_code_repository.verify_code(email=email, purpose=purpose, code=code)
        if not auth_code:
            raise ValidationException('Invalid or expired verification code')
        await self.auth_code_repository.consume_code(auth_code['_id'])

    def _build_auth_response(self, user: dict) -> AuthResponse:
        public_user = self._to_auth_user_response(user)
        return AuthResponse(
            user=public_user,
            tokens=self._build_tokens(public_user.id, public_user.role),
        )

    def _to_auth_user_response(self, user: dict) -> AuthUserResponse:
        serialized = self.serialize(user)
        return AuthUserResponse(
            id=serialized['id'],
            email=serialized['email'],
            full_name=serialized['full_name'],
            phone=serialized.get('phone'),
            role=serialized['role'],
            preferred_language=serialized.get('preferred_language', AppLanguage.ENGLISH),
            is_active=serialized['is_active'],
            email_verified=serialized.get('email_verified', False),
            restaurant_name=serialized.get('restaurant_name'),
            location=serialized.get('location'),
            subscription_plan_name=serialized.get('subscription_plan_name'),
            subscription_plan=serialized.get('subscription_plan'),
            subscription_status=serialized.get('subscription_status'),
            subscription_started_at=serialized.get('subscription_started_at'),
            subscription_expires_at=serialized.get('subscription_expires_at'),
            subscription_selection_required=self._requires_subscription_selection(serialized),
            created_at=serialized['created_at'],
            updated_at=serialized['updated_at'],
        )

    def _requires_subscription_selection(self, serialized_user: dict) -> bool:
        return serialized_user['role'] in self.RESTAURANT_AUTH_ROLES and not serialized_user.get('subscription_plan_name')

    @staticmethod
    def _build_tokens(user_id: str, role: str) -> TokenResponse:
        return TokenResponse(
            access_token=token_manager.create_access_token(subject=user_id, role=role),
            refresh_token=token_manager.create_refresh_token(subject=user_id, role=role),
        )
