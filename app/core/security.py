from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext

from app.config.settings import get_settings
from app.core.exceptions import AuthenticationException

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class PasswordManager:
    """Encapsulates password hashing and verification."""

    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)


class TokenManager:
    """Factory-style helper for JWT token generation and validation."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def create_access_token(self, subject: str, role: str) -> str:
        expires_at = datetime.now(UTC) + timedelta(minutes=self.settings.access_token_expiry_minutes)
        return self._encode_token({"sub": subject, "role": role, "type": "access", "exp": expires_at})

    def create_refresh_token(self, subject: str, role: str) -> str:
        expires_at = datetime.now(UTC) + timedelta(days=self.settings.refresh_token_expiry_days)
        return self._encode_token({"sub": subject, "role": role, "type": "refresh", "exp": expires_at})

    def decode_token(self, token: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret,
                algorithms=[self.settings.jwt_algorithm],
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationException("Invalid or expired token") from exc
        return payload

    def _encode_token(self, payload: dict[str, Any]) -> str:
        return jwt.encode(payload, self.settings.jwt_secret, algorithm=self.settings.jwt_algorithm)


password_manager = PasswordManager()
token_manager = TokenManager()
