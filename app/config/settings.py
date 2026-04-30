from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import EmailStr, Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Environment-driven application settings."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "RistoAI"
    app_version: str = "1.0.0"
    debug: bool = False
    testing: bool = False
    log_level: str = Field(default="ERROR", alias="LOG_LEVEL")
    request_logs_enabled: bool = Field(default=False, alias="REQUEST_LOGS_ENABLED")

    mongodb_uri: str = Field(default="mongodb://localhost:27017", alias="MONGODB_URI")
    database_name: str = Field(default="ristoai", alias="DATABASE_NAME")

    jwt_secret: str = Field(default="change-me", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expiry_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRY_MINUTES")
    refresh_token_expiry_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRY_DAYS")

    cors_origins: list[str] = Field(default_factory=lambda: ["*"], alias="CORS_ORIGINS")
    cors_allow_origin_regex: str | None = Field(
        default=r"https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+|192\.168\.\d+\.\d+)(:\d+)?",
        alias="CORS_ALLOW_ORIGIN_REGEX",
    )

    smtp_enabled: bool = Field(default=False, alias="SMTP_ENABLED")
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_from_email: EmailStr | None = Field(default=None, alias="SMTP_FROM_EMAIL")
    smtp_from_name: str = Field(default="RistoAI", alias="SMTP_FROM_NAME")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")
    smtp_use_ssl: bool = Field(default=False, alias="SMTP_USE_SSL")

    super_admin_email: EmailStr | None = Field(default=None, alias="SUPER_ADMIN_EMAIL")
    super_admin_password: str | None = Field(default=None, alias="SUPER_ADMIN_PASSWORD")
    super_admin_full_name: str = Field(default="Super Admin", alias="SUPER_ADMIN_FULL_NAME")

    subscription_plan_name: str = Field(default="Core Plan", alias="SUBSCRIPTION_PLAN_NAME")
    subscription_plan_monthly_price: float = Field(default=30.0, alias="SUBSCRIPTION_PLAN_MONTHLY_PRICE")
    subscription_plan_annual_price: float = Field(default=350.0, alias="SUBSCRIPTION_PLAN_ANNUAL_PRICE")
    subscription_plan_trial_days: int = Field(default=7, alias="SUBSCRIPTION_PLAN_TRIAL_DAYS")
    subscription_plan_features: list[str] = Field(
        default_factory=lambda: ["AI menu suggestions", "Basic sales analytics", "Email support"],
        alias="SUBSCRIPTION_PLAN_FEATURES",
    )
    subscription_plan_is_visible: bool = Field(default=True, alias="SUBSCRIPTION_PLAN_IS_VISIBLE")
    subscription_plan_is_active: bool = Field(default=True, alias="SUBSCRIPTION_PLAN_IS_ACTIVE")
    subscription_plan_is_best: bool = Field(default=False, alias="SUBSCRIPTION_PLAN_IS_BEST")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")

    aws_access_key_id: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    aws_s3_bucket: str | None = Field(default=None, alias="AWS_S3_BUCKET")
    aws_region: str | None = Field(default=None, alias="AWS_REGION")

    stripe_secret_key: str | None = Field(default=None, alias="STRIPE_SECRET_KEY")
    stripe_publishable_key: str | None = Field(default=None, alias="STRIPE_PUBLISHABLE_KEY")
    stripe_webhook_secret: str | None = Field(default=None, alias="STRIPE_WEBHOOK_SECRET")
    stripe_price_id_monthly: str | None = Field(default=None, alias="STRIPE_PRICE_ID_MONTHLY")
    stripe_price_id_yearly: str | None = Field(default=None, alias="STRIPE_PRICE_ID_YEARLY")
    stripe_checkout_success_url: str = Field(default="http://localhost:3000/subscription/success", alias="STRIPE_CHECKOUT_SUCCESS_URL")
    stripe_checkout_cancel_url: str = Field(default="http://localhost:3000/subscription/cancel", alias="STRIPE_CHECKOUT_CANCEL_URL")
    stripe_customer_portal_return_url: str = Field(default="http://localhost:3000/settings/subscription", alias="STRIPE_CUSTOMER_PORTAL_RETURN_URL")

    @computed_field
    @property
    def openapi_url(self) -> str:
        return "/openapi.json"

    @model_validator(mode="after")
    def validate_smtp_settings(self) -> "Settings":
        if self.smtp_use_tls and self.smtp_use_ssl:
            raise ValueError("SMTP_USE_TLS and SMTP_USE_SSL cannot both be true")
        if self.smtp_enabled:
            required_fields = {
                "SMTP_HOST": self.smtp_host,
                "SMTP_USERNAME": self.smtp_username,
                "SMTP_PASSWORD": self.smtp_password,
                "SMTP_FROM_EMAIL": self.smtp_from_email,
            }
            missing_fields = [key for key, value in required_fields.items() if not value]
            if missing_fields:
                raise ValueError(
                    f"SMTP is enabled but required settings are missing: {', '.join(missing_fields)}",
                )
        return self

    @model_validator(mode="after")
    def validate_super_admin_settings(self) -> "Settings":
        if bool(self.super_admin_email) != bool(self.super_admin_password):
            raise ValueError("SUPER_ADMIN_EMAIL and SUPER_ADMIN_PASSWORD must both be set together")
        if self.subscription_plan_trial_days < 0 or self.subscription_plan_trial_days > 365:
            raise ValueError("SUBSCRIPTION_PLAN_TRIAL_DAYS must be between 0 and 365")
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> tuple[Any, ...]:
        return init_settings, env_settings, dotenv_settings, file_secret_settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()



