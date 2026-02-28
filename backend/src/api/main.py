"""FastAPI application factory and lifespan management."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.src.api.ingest_routes import ingest_router
from backend.src.api.query_routes import limiter, query_router
from backend.src.api.routes import router
from backend.src.core.config import Settings, get_settings
from backend.src.core.log import configure_logging
from backend.src.core.security import PromptInjectionError
from backend.src.core.telemetry import configure_telemetry, instrument_fastapi, shutdown_telemetry
from backend.src.models.schemas import ErrorResponse

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Application startup and shutdown lifecycle."""
    settings = get_settings()
    configure_logging(log_level=settings.log_level, log_format=settings.log_format)
    configure_telemetry(settings)
    logger.info("app_starting", app_name=settings.app_name)
    yield
    shutdown_telemetry()
    logger.info("app_shutting_down")


def create_app() -> FastAPI:
    """Build and return a fully-configured FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    _add_middleware(app, settings)
    _add_exception_handlers(app)
    _include_routers(app)
    instrument_fastapi(app, settings)

    return app


def _add_middleware(app: FastAPI, settings: Settings) -> None:
    """Register all middleware on the application."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(GZipMiddleware, minimum_size=1000)

    if settings.allowed_hosts != "*":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.allowed_hosts.split(","),
        )

    @app.middleware("http")
    async def request_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response: Response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response


def _add_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers."""
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content=ErrorResponse(
                error="rate_limit_exceeded",
                detail=str(exc.detail),
                request_id=request.headers.get("x-request-id"),
            ).model_dump(),
        )

    @app.exception_handler(PromptInjectionError)
    async def injection_handler(request: Request, exc: PromptInjectionError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error="prompt_injection_detected",
                detail=str(exc),
                request_id=request.headers.get("x-request-id"),
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = request.headers.get("x-request-id")
        logger.exception("unhandled_exception", request_id=request_id, error=str(exc))
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_server_error",
                detail="An unexpected error occurred.",
                request_id=request_id,
            ).model_dump(),
        )


def _include_routers(app: FastAPI) -> None:
    """Mount all API routers."""
    app.include_router(router)
    app.include_router(ingest_router)
    app.include_router(query_router)
