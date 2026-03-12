from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field, field_validator, model_validator

from app.core.enums import AppLanguage, SubscriptionPlan, SubscriptionStatus, UserRole
from app.schemas.common import BaseSchema



def validate_password_strength(value: str) -> str:
    if not any(char.isdigit() for char in value) or not any(char.isalpha() for char in value):
        raise ValueError('Password must include letters and numbers')
    return value


class RegisterRequest(BaseSchema):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    phone: str | None = Field(default=None, max_length=30)

    @field_validator('password')
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)


class LoginRequest(BaseSchema):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class VerifyCodeRequest(BaseSchema):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)

    @field_validator('code')
    @classmethod
    def validate_numeric_code(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError('Verification code must be numeric')
        return value


class ForgotPasswordRequest(BaseSchema):
    email: EmailStr


class ResetPasswordRequest(BaseSchema):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8, max_length=72)
    confirm_password: str = Field(min_length=8, max_length=72)

    @field_validator('code')
    @classmethod
    def validate_reset_code(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError('Verification code must be numeric')
        return value

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return validate_password_strength(value)

    @model_validator(mode='after')
    def validate_password_match(self) -> 'ResetPasswordRequest':
        if self.new_password != self.confirm_password:
            raise ValueError('New password and confirm password must match')
        return self


class RefreshTokenRequest(BaseSchema):
    refresh_token: str


class UpdateLanguagePreferenceRequest(BaseSchema):
    preferred_language: AppLanguage


class TokenResponse(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'


class AuthChallengeResponse(BaseSchema):
    message: str
    verification_required: bool = True
    purpose: str
    email: EmailStr
    expires_in_seconds: int
    debug_verification_code: str | None = None


class LanguagePreferenceResponse(BaseSchema):
    preferred_language: AppLanguage


class AuthUserResponse(BaseSchema):
    id: str
    email: EmailStr
    full_name: str
    phone: str | None = None
    role: UserRole
    preferred_language: AppLanguage
    is_active: bool
    email_verified: bool
    restaurant_name: str | None = None
    location: str | None = None
    subscription_plan_name: str | None = None
    subscription_plan: SubscriptionPlan | None = None
    subscription_status: SubscriptionStatus | None = None
    subscription_started_at: datetime | None = None
    subscription_expires_at: datetime | None = None
    subscription_selection_required: bool
    created_at: str
    updated_at: str


class AuthResponse(BaseSchema):
    user: AuthUserResponse
    tokens: TokenResponse
