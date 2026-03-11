from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import EmailStr, Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "RistoAI"
    app_version: str = "1.0.0"
    debug: bool = False
    testing: bool = False

    mongodb_uri: str = Field(default="mongodb://localhost:27017", alias="MONGODB_URI")
    database_name: str = Field(default="ristoai", alias="DATABASE_NAME")

    jwt_secret: str = Field(default="change-me", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expiry_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRY_MINUTES")
    refresh_token_expiry_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRY_DAYS")

    cors_origins: list[str] = Field(default_factory=lambda: ["*"], alias="CORS_ORIGINS")
    ai_chat_provider: str = Field(default="mock", alias="AI_CHAT_PROVIDER")
    ai_chat_model_id: str = Field(default="meta-llama/Llama-3.1-8B-Instruct", alias="AI_CHAT_MODEL_ID")
    ai_chat_max_new_tokens: int = Field(default=256, alias="AI_CHAT_MAX_NEW_TOKENS")
    ai_chat_temperature: float = Field(default=0.2, alias="AI_CHAT_TEMPERATURE")
    huggingface_token: str | None = Field(default=None, alias="HUGGINGFACE_TOKEN")

    smtp_enabled: bool = Field(default=False, alias="SMTP_ENABLED")
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_from_email: EmailStr | None = Field(default=None, alias="SMTP_FROM_EMAIL")
    smtp_from_name: str = Field(default="RistoAI", alias="SMTP_FROM_NAME")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")
    smtp_use_ssl: bool = Field(default=False, alias="SMTP_USE_SSL")

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
