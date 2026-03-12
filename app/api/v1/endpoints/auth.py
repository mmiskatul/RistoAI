from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_auth_service
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
from app.services.auth import AuthService

router = APIRouter()


@router.post('/restaurant/register', response_model=AuthChallengeResponse, status_code=status.HTTP_201_CREATED, tags=['Restaurant Authentication'])
async def register_restaurant(
    payload: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthChallengeResponse:
    return await service.register_restaurant(payload)


@router.post('/restaurant/verify-registration', response_model=AuthResponse, tags=['Restaurant Authentication'])
async def verify_restaurant_registration(
    payload: VerifyCodeRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    return await service.verify_restaurant_registration(payload)


@router.post('/restaurant/login', response_model=AuthResponse, tags=['Restaurant Authentication'])
async def login_restaurant(
    payload: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    return await service.login_restaurant(payload)


@router.post('/restaurant/forgot-password', response_model=AuthChallengeResponse, tags=['Restaurant Authentication'])
async def forgot_password_restaurant(
    payload: ForgotPasswordRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthChallengeResponse:
    return await service.forgot_password_restaurant(payload)


@router.post('/restaurant/reset-password', response_model=MessageResponse, tags=['Restaurant Authentication'])
async def reset_password_restaurant(
    payload: ResetPasswordRequest,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    return await service.reset_password_restaurant(payload)


@router.post('/admin/login', response_model=AuthResponse, tags=['Admin Authentication'])
async def login_admin(
    payload: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    return await service.login_admin(payload)


@router.post('/admin/forgot-password', response_model=AuthChallengeResponse, tags=['Admin Authentication'])
async def forgot_password_admin(
    payload: ForgotPasswordRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthChallengeResponse:
    return await service.forgot_password_admin(payload)


@router.post('/admin/reset-password', response_model=MessageResponse, tags=['Admin Authentication'])
async def reset_password_admin(
    payload: ResetPasswordRequest,
    service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    return await service.reset_password_admin(payload)


@router.post('/refresh', response_model=TokenResponse, tags=['Authentication'])
async def refresh(payload: RefreshTokenRequest, service: AuthService = Depends(get_auth_service)) -> TokenResponse:
    return await service.refresh(payload)


@router.get('/me', response_model=AuthUserResponse, tags=['Authentication'])
async def me(current_user: dict = Depends(get_current_user), service: AuthService = Depends(get_auth_service)) -> AuthUserResponse:
    return await service.get_me(current_user)


@router.get('/preferences/language', response_model=LanguagePreferenceResponse, tags=['Authentication'])
async def get_language_preference(
    current_user: dict = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> LanguagePreferenceResponse:
    return await service.get_language_preference(current_user)


@router.put('/preferences/language', response_model=LanguagePreferenceResponse, tags=['Authentication'])
async def update_language_preference(
    payload: UpdateLanguagePreferenceRequest,
    current_user: dict = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> LanguagePreferenceResponse:
    return await service.update_language_preference(current_user, payload)
