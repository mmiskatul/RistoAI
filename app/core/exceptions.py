from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AppException(Exception):
    """Base exception used to produce consistent API errors."""

    status_code: int
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found", details: dict[str, Any] | None = None) -> None:
        super().__init__(status_code=404, code="not_found", message=message, details=details or {})


class ConflictException(AppException):
    def __init__(self, message: str = "Resource conflict", details: dict[str, Any] | None = None) -> None:
        super().__init__(status_code=409, code="conflict", message=message, details=details or {})


class AuthorizationException(AppException):
    def __init__(self, message: str = "Not authorized", details: dict[str, Any] | None = None) -> None:
        super().__init__(status_code=403, code="forbidden", message=message, details=details or {})


class AuthenticationException(AppException):
    def __init__(self, message: str = "Authentication failed", details: dict[str, Any] | None = None) -> None:
        super().__init__(status_code=401, code="unauthorized", message=message, details=details or {})


class ValidationException(AppException):
    def __init__(self, message: str = "Validation failed", details: dict[str, Any] | None = None) -> None:
        super().__init__(status_code=422, code="validation_error", message=message, details=details or {})
