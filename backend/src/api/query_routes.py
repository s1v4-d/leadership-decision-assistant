"""Query API routes with SSE streaming, Redis caching, and rate limiting."""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Request
from redis.asyncio import Redis
from slowapi import Limiter
from slowapi.util import get_remote_address
from sse_starlette import EventSourceResponse, ServerSentEvent

from backend.src.api.dependencies import SettingsDep  # noqa: TC001
from backend.src.models.schemas import QueryRequest, QueryResponse, SourceNodeResponse
from backend.src.tools.rag_tool import execute_query

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = structlog.get_logger(__name__)

limiter = Limiter(key_func=get_remote_address)

query_router = APIRouter(prefix="/api/v1", tags=["query"])


def _get_redis_client(settings: SettingsDep) -> Redis | None:
    """Create an async Redis client, returning None if unavailable."""
    try:
        return Redis.from_url(settings.redis.url, decode_responses=True)
    except Exception:
        logger.warning("redis_unavailable")
        return None


def _build_cache_key(query_text: str) -> str:
    return "query:" + hashlib.sha256(query_text.encode()).hexdigest()


def _build_query_response(
    answer: str,
    sources: list[SourceNodeResponse],
    *,
    cached: bool = False,
) -> QueryResponse:
    return QueryResponse(answer=answer, sources=sources, cached=cached)


async def _check_cache(redis_client: Redis | None, cache_key: str) -> QueryResponse | None:
    if redis_client is None:
        return None
    try:
        cached = await redis_client.get(cache_key)
        if cached is not None:
            data = json.loads(cached)
            return QueryResponse(**data)
    except Exception:
        logger.warning("cache_read_failed", cache_key=cache_key)
    return None


async def _store_cache(
    redis_client: Redis | None,
    cache_key: str,
    response: QueryResponse,
    ttl_seconds: int,
) -> None:
    if redis_client is None:
        return
    try:
        await redis_client.setex(cache_key, ttl_seconds, response.model_dump_json())
    except Exception:
        logger.warning("cache_write_failed", cache_key=cache_key)


async def _run_query(query_text: str, settings: SettingsDep) -> QueryResponse:
    result = await asyncio.to_thread(execute_query, query_text, settings)
    sources = [
        SourceNodeResponse(text=node.text, score=node.score, metadata=node.metadata) for node in result.source_nodes
    ]
    return _build_query_response(result.answer, sources)


async def _stream_query_events(query_text: str, settings: SettingsDep) -> AsyncGenerator[ServerSentEvent]:
    response = await _run_query(query_text, settings)

    yield ServerSentEvent(data=response.answer, event="answer")

    sources_data = [s.model_dump() for s in response.sources]
    yield ServerSentEvent(data=json.dumps(sources_data), event="sources")

    yield ServerSentEvent(data="", event="done")


@query_router.post("/query", response_model=QueryResponse)
@limiter.limit("20/minute")  # type: ignore[misc]
async def query_documents(
    request: Request,  # noqa: ARG001  # required by SlowAPI limiter
    body: QueryRequest,
    settings: SettingsDep,
) -> QueryResponse | EventSourceResponse:
    """Execute a RAG query, with optional SSE streaming and Redis caching."""
    logger.info("query_received", query_length=len(body.query), stream=body.stream)

    redis_client = _get_redis_client(settings)
    cache_key = _build_cache_key(body.query)

    if body.stream:
        return EventSourceResponse(_stream_query_events(body.query, settings))

    cached_response = await _check_cache(redis_client, cache_key)
    if cached_response is not None:
        logger.info("cache_hit", cache_key=cache_key)
        return cached_response

    response = await _run_query(body.query, settings)

    await _store_cache(redis_client, cache_key, response, settings.redis.ttl_seconds)

    logger.info("query_complete", answer_length=len(response.answer))
    return response
