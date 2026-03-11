from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.config.settings import get_settings
from app.core.constants import API_V1_PREFIX
from app.core.exceptions import AppException
from app.core.logging import configure_logging
from app.db.indexes import ensure_indexes
from app.db.mongodb import MongoDB
from app.middleware.request_context import RequestContextMiddleware

logger = logging.getLogger(__name__)



def create_app(*, testing: bool = False) -> FastAPI:
    settings = get_settings()
    settings.testing = testing
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if not settings.testing:
            db = MongoDB.connect(settings)
            await ensure_indexes(db)
            logger.info("MongoDB connected and indexes ensured")
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
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "details": {"errors": jsonable_encoder(exc.errors())},
                },
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {"code": "internal_server_error", "message": "Unexpected server error", "details": {}},
            },
        )

    @app.get("/health", tags=["Health"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    return app


app = create_app()
