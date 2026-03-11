from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config.settings import Settings, get_settings


class MongoDB:
    """Singleton-style MongoDB client manager shared across the app."""

    _client: AsyncIOMotorClient | None = None

    @classmethod
    def connect(cls, settings: Settings | None = None) -> AsyncIOMotorDatabase:
        resolved_settings = settings or get_settings()
        if cls._client is None:
            cls._client = AsyncIOMotorClient(resolved_settings.mongodb_uri)
        return cls._client[resolved_settings.database_name]

    @classmethod
    def get_database(cls, settings: Settings | None = None) -> AsyncIOMotorDatabase:
        return cls.connect(settings)

    @classmethod
    def close(cls) -> None:
        if cls._client is not None:
            cls._client.close()
            cls._client = None


async def get_database() -> AsyncIOMotorDatabase:
    return MongoDB.get_database()
