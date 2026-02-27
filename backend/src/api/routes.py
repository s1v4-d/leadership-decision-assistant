"""API route definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import asyncpg
import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.src.api.dependencies import SettingsDep  # noqa: TC001
from backend.src.models.schemas import HealthResponse, ReadyResponse

if TYPE_CHECKING:
    from backend.src.core.config import Settings

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Lightweight liveness check."""
    return HealthResponse(
        status="ok",
        app_name="leadership-insight-agent",
        version="0.1.0",
    )


@router.get("/ready", response_model=ReadyResponse)
async def ready(settings: SettingsDep) -> JSONResponse:
    """Readiness check that verifies external dependency connectivity."""
    pg_ok = await _check_postgres(settings)
    redis_ok = await _check_redis(settings)
    checks = {"postgres": pg_ok, "redis": redis_ok}
    all_ok = all(checks.values())

    if not all_ok:
        logger.warning("readiness_check_failed", checks=checks)

    return JSONResponse(
        status_code=200 if all_ok else 503,
        content=ReadyResponse(
            status="ok" if all_ok else "degraded",
            checks=checks,
        ).model_dump(),
    )


async def _check_postgres(settings: Settings) -> bool:
    """Attempt a lightweight PostgreSQL connection check."""
    try:
        pg = settings.postgres
        conn = await asyncpg.connect(
            host=pg.host,
            port=pg.port,
            user=pg.user,
            password=pg.password.get_secret_value(),
            database=pg.database,
        )
        await conn.execute("SELECT 1")
        await conn.close()
    except Exception:
        logger.debug("postgres_check_failed", exc_info=True)
        return False
    else:
        return True


async def _check_redis(settings: Settings) -> bool:
    """Attempt a lightweight Redis ping."""
    try:
        client = aioredis.from_url(settings.redis.url)
        await client.ping()  # type: ignore[misc]
        await client.aclose()
    except Exception:
        logger.debug("redis_check_failed", exc_info=True)
        return False
    else:
        return True
