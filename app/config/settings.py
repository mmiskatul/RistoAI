from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field, computed_field
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

    @computed_field
    @property
    def openapi_url(self) -> str:
        return "/openapi.json"

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
