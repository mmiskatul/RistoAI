from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Adds request IDs and optional access logging for traceability."""

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start_time = time.perf_counter()
        client_host = request.client.host if request.client else "unknown"

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            if settings.request_logs_enabled:
                logger.exception(
                    "request_id=%s client=%s %s %s -> 500 in %sms",
                    request_id,
                    client_host,
                    request.method,
                    request.url.path,
                    duration_ms,
                )
            raise

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        if settings.request_logs_enabled:
            logger.info(
                "request_id=%s client=%s %s %s -> %s in %sms",
                request_id,
                client_host,
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
        return response
