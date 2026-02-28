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

from backend.src.api.dependencies import SessionDep, SettingsDep  # noqa: TC001
from backend.src.core.security import (
    PromptInjectionError,
    detect_prompt_injection,
    parse_blocked_patterns,
    sanitize_query,
)
from backend.src.models.schemas import QueryRequest, QueryResponse, SourceNodeResponse
from backend.src.models.tables import Collection
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


def secure_query_input(query_text: str, settings: SettingsDep) -> str:
    """Sanitize input and check for prompt injection."""
    sanitized = sanitize_query(query_text, max_length=settings.security.max_query_length)
    blocked = parse_blocked_patterns(settings.security.blocked_patterns)
    if detect_prompt_injection(sanitized, blocked):
        raise PromptInjectionError("Prompt injection detected in query")
    return sanitized


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


def _resolve_vector_table(
    collection_id: str | None,
    session: SessionDep,
) -> str | None:
    """Resolve a collection_id to its vector table name, or None for default."""
    if collection_id is None:
        return None
    collection = session.get(Collection, collection_id)
    if collection is None:
        return None
    return collection.vector_table


async def _run_query(
    query_text: str,
    settings: SettingsDep,
    *,
    table_name: str | None = None,
) -> QueryResponse:
    result = await asyncio.to_thread(execute_query, query_text, settings, table_name=table_name)
    sources = [
        SourceNodeResponse(text=node.text, score=node.score, metadata=node.metadata) for node in result.source_nodes
    ]
    return _build_query_response(result.answer, sources)


async def _stream_query_events(
    query_text: str,
    settings: SettingsDep,
    *,
    table_name: str | None = None,
) -> AsyncGenerator[ServerSentEvent]:
    response = await _run_query(query_text, settings, table_name=table_name)

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
    session: SessionDep,
) -> QueryResponse | EventSourceResponse:
    """Execute a RAG query, with optional SSE streaming and Redis caching."""
    logger.info("query_received", query_length=len(body.query), stream=body.stream)

    sanitized_query = secure_query_input(body.query, settings)

    table_name = _resolve_vector_table(body.collection_id, session)

    redis_client = _get_redis_client(settings)
    cache_key = _build_cache_key(sanitized_query)

    if body.stream:
        return EventSourceResponse(_stream_query_events(sanitized_query, settings, table_name=table_name))

    cached_response = await _check_cache(redis_client, cache_key)
    if cached_response is not None:
        logger.info("cache_hit", cache_key=cache_key)
        return cached_response

    response = await _run_query(sanitized_query, settings, table_name=table_name)

    await _store_cache(redis_client, cache_key, response, settings.redis.ttl_seconds)

    logger.info("query_complete", answer_length=len(response.answer))
    return response
