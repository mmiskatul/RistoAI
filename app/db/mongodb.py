from __future__ import annotations

import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class MongoDB:
    """Singleton-style MongoDB client manager shared across the app."""

    _client: AsyncIOMotorClient | None = None

    @classmethod
    def connect(cls, settings: Settings | None = None) -> AsyncIOMotorDatabase:
        resolved_settings = settings or get_settings()
        if cls._client is None:
            cls._client = AsyncIOMotorClient(
                resolved_settings.mongodb_uri,
                appname=resolved_settings.app_name,
                maxPoolSize=resolved_settings.mongodb_max_pool_size,
                minPoolSize=resolved_settings.mongodb_min_pool_size,
                connectTimeoutMS=resolved_settings.mongodb_connect_timeout_ms,
                serverSelectionTimeoutMS=resolved_settings.mongodb_server_selection_timeout_ms,
                retryWrites=True,
                tz_aware=True,
            )
        return cls._client[resolved_settings.database_name]

    @classmethod
    def get_database(cls, settings: Settings | None = None) -> AsyncIOMotorDatabase:
        return cls.connect(settings)

    @classmethod
    async def ping(cls, settings: Settings | None = None) -> bool:
        try:
            db = cls.get_database(settings)
            await db.command("ping")
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("MongoDB ping failed: %s", exc)
            return False

    @classmethod
    def close(cls) -> None:
        if cls._client is not None:
            cls._client.close()
            cls._client = None


async def get_database() -> AsyncIOMotorDatabase:
    return MongoDB.get_database()
