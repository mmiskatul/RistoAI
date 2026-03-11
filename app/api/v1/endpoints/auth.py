from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_auth_service
from app.schemas.auth import AuthResponse, AuthUserResponse, LoginRequest, RefreshTokenRequest, RegisterRequest, TokenResponse
from app.services.auth import AuthService

router = APIRouter()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, service: AuthService = Depends(get_auth_service)) -> AuthResponse:
    return await service.register(payload)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, service: AuthService = Depends(get_auth_service)) -> AuthResponse:
    return await service.login(payload)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshTokenRequest, service: AuthService = Depends(get_auth_service)) -> TokenResponse:
    return await service.refresh(payload)


@router.get("/me", response_model=AuthUserResponse)
async def me(current_user: dict = Depends(get_current_user), service: AuthService = Depends(get_auth_service)) -> AuthUserResponse:
    return await service.get_me(current_user)
