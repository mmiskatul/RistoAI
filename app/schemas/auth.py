from __future__ import annotations

from pydantic import EmailStr, Field, field_validator

from app.core.enums import UserRole
from app.schemas.common import BaseSchema


class RegisterRequest(BaseSchema):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not any(char.isdigit() for char in value) or not any(char.isalpha() for char in value):
            raise ValueError("Password must include letters and numbers")
        return value


class LoginRequest(BaseSchema):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshTokenRequest(BaseSchema):
    refresh_token: str


class TokenResponse(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthUserResponse(BaseSchema):
    id: str
    email: EmailStr
    full_name: str
    phone: str | None = None
    role: UserRole
    is_active: bool
    restaurant_ids: list[str] = Field(default_factory=list)
    branch_ids: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class AuthResponse(BaseSchema):
    user: AuthUserResponse
    tokens: TokenResponse
