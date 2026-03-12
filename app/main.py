from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.config.settings import get_settings
from app.core.constants import API_V1_PREFIX
from app.core.exceptions import AppException
from app.core.logging import configure_logging
from app.db.indexes import ensure_indexes
from app.db.mongodb import MongoDB
from app.middleware.request_context import RequestContextMiddleware
from app.repositories.user import UserRepository
from app.services.bootstrap import BootstrapService

logger = logging.getLogger(__name__)



def _make_json_safe(value: Any) -> Any:
    if isinstance(value, BaseException):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _make_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_make_json_safe(item) for item in value]
    return jsonable_encoder(value)



def _error_response(status_code: int, code: str, message: str, details: dict[str, Any] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": {"code": code, "message": message, "details": details or {}}},
    )



def _http_error_code(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        422: "validation_error",
    }.get(status_code, "http_error")



def _split_http_detail(detail: Any) -> tuple[str, dict[str, Any]]:
    safe_detail = _make_json_safe(detail)
    if isinstance(safe_detail, str):
        return safe_detail, {}
    return "Request failed", {"detail": safe_detail}



def create_app(*, testing: bool = False) -> FastAPI:
    settings = get_settings()
    settings.testing = testing
    if testing:
        settings.smtp_enabled = False
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if not settings.testing:
            db = MongoDB.connect(settings)
            await ensure_indexes(db)
            await BootstrapService(UserRepository(db)).ensure_super_admin(settings)
            logger.info("MongoDB connected, indexes ensured, and super admin synchronized")
        yield
        if not settings.testing:
            MongoDB.close()
            logger.info("MongoDB connection closed")

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        openapi_url=settings.openapi_url,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)
    app.include_router(api_router, prefix=API_V1_PREFIX)

    @app.exception_handler(AppException)
    async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
        return _error_response(exc.status_code, exc.code, exc.message, _make_json_safe(exc.details))

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        message, details = _split_http_detail(exc.detail)
        return _error_response(exc.status_code, _http_error_code(exc.status_code), message, details)

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(
            422,
            "validation_error",
            "Request validation failed",
            {"errors": _make_json_safe(exc.errors())},
        )

    @app.exception_handler(ResponseValidationError)
    async def response_validation_exception_handler(_: Request, exc: ResponseValidationError) -> JSONResponse:
        logger.exception("Response validation failed", exc_info=exc)
        return _error_response(
            500,
            "response_validation_error",
            "Response validation failed",
            {"errors": _make_json_safe(exc.errors())},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server error", exc_info=exc)
        return _error_response(500, "internal_server_error", "Unexpected server error")

    @app.get("/", tags=["root"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    return app


app = create_app()
