"""TDD tests for query API endpoint with streaming, caching, and rate limiting."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.src.core.config import Settings

if TYPE_CHECKING:
    from fastapi import FastAPI


def _mock_session() -> MagicMock:
    from unittest.mock import MagicMock

    return MagicMock()


def _create_test_app() -> FastAPI:
    from backend.src.api.dependencies import get_session
    from backend.src.api.main import create_app

    app = create_app()
    app.dependency_overrides[get_session] = _mock_session
    return app


def _make_settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, openai_api_key="sk-test", **overrides)  # pragma: allowlist secret


class TestQueryRequest:
    def test_query_request_has_required_fields(self) -> None:
        from backend.src.models.schemas import QueryRequest

        req = QueryRequest(query="What is the strategy?")
        assert req.query == "What is the strategy?"
        assert req.stream is False

    def test_query_request_stream_defaults_false(self) -> None:
        from backend.src.models.schemas import QueryRequest

        req = QueryRequest(query="test")
        assert req.stream is False

    def test_query_request_stream_can_be_true(self) -> None:
        from backend.src.models.schemas import QueryRequest

        req = QueryRequest(query="test", stream=True)
        assert req.stream is True


class TestQueryResponse:
    def test_query_response_has_required_fields(self) -> None:
        from backend.src.models.schemas import QueryResponse, SourceNodeResponse

        resp = QueryResponse(
            answer="Revenue was $127M.",
            sources=[SourceNodeResponse(text="doc text", score=0.9, metadata={})],
            cached=False,
        )
        assert resp.answer == "Revenue was $127M."
        assert len(resp.sources) == 1
        assert resp.cached is False

    def test_query_response_cached_defaults_false(self) -> None:
        from backend.src.models.schemas import QueryResponse

        resp = QueryResponse(answer="test", sources=[])
        assert resp.cached is False

    def test_source_node_response_has_fields(self) -> None:
        from backend.src.models.schemas import SourceNodeResponse

        node = SourceNodeResponse(text="chunk", score=0.85, metadata={"file": "a.pdf"})
        assert node.text == "chunk"
        assert node.score == 0.85
        assert node.metadata == {"file": "a.pdf"}


class TestQueryEndpoint:
    @pytest.fixture
    def app(self) -> FastAPI:
        return _create_test_app()

    @pytest.fixture
    def settings(self) -> Settings:
        return _make_settings()

    @patch("backend.src.api.query_routes._get_redis_client", return_value=None)
    @patch("backend.src.api.query_routes.execute_query")
    async def test_query_returns_200_with_answer(
        self, mock_execute: MagicMock, mock_redis: MagicMock, app: FastAPI
    ) -> None:
        from backend.src.models.domain import QueryResult, SourceNode

        mock_execute.return_value = QueryResult(
            answer="The strategy focuses on AI.",
            source_nodes=[SourceNode(text="doc text", score=0.9, metadata={})],
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/query", json={"query": "What is the strategy?"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "The strategy focuses on AI."
        assert len(data["sources"]) == 1
        assert data["cached"] is False

    @patch("backend.src.api.query_routes._get_redis_client", return_value=None)
    @patch("backend.src.api.query_routes.execute_query")
    async def test_query_calls_execute_query_with_text(
        self, mock_execute: MagicMock, mock_redis: MagicMock, app: FastAPI
    ) -> None:
        from backend.src.models.domain import QueryResult

        mock_execute.return_value = QueryResult(answer="ok", source_nodes=[])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/v1/query", json={"query": "test question"})

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args
        assert call_args[0][0] == "test question"

    @patch("backend.src.api.query_routes._get_redis_client", return_value=None)
    async def test_query_rejects_empty_query(self, mock_redis: MagicMock, app: FastAPI) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/query", json={"query": ""})

        assert resp.status_code == 422

    @patch("backend.src.api.query_routes._get_redis_client", return_value=None)
    async def test_query_rejects_too_long_query(self, mock_redis: MagicMock, app: FastAPI) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/query", json={"query": "x" * 2001})

        assert resp.status_code == 422

    @patch("backend.src.api.query_routes._get_redis_client", return_value=None)
    @patch("backend.src.api.query_routes.execute_query")
    async def test_query_audit_logs_request(self, mock_execute: MagicMock, mock_redis: MagicMock, app: FastAPI) -> None:
        from backend.src.models.domain import QueryResult

        mock_execute.return_value = QueryResult(answer="ok", source_nodes=[])

        transport = ASGITransport(app=app)
        with patch("backend.src.api.query_routes.logger") as mock_logger:
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                await client.post("/api/v1/query", json={"query": "audit test"})

            mock_logger.info.assert_any_call(
                "query_received",
                query_length=10,
                stream=False,
            )


class TestRedisCaching:
    @pytest.fixture
    def app(self) -> FastAPI:
        return _create_test_app()

    @patch("backend.src.api.query_routes.execute_query")
    @patch("backend.src.api.query_routes._get_redis_client")
    async def test_returns_cached_response_on_hit(
        self, mock_get_redis: MagicMock, mock_execute: MagicMock, app: FastAPI
    ) -> None:
        cached_data = json.dumps(
            {
                "answer": "cached answer",
                "sources": [{"text": "cached text", "score": 0.8, "metadata": {}}],
                "cached": True,
            }
        )
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=cached_data)
        mock_get_redis.return_value = mock_redis

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/query", json={"query": "cached query"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "cached answer"
        assert data["cached"] is True
        mock_execute.assert_not_called()

    @patch("backend.src.api.query_routes.execute_query")
    @patch("backend.src.api.query_routes._get_redis_client")
    async def test_stores_result_in_cache_on_miss(
        self, mock_get_redis: MagicMock, mock_execute: MagicMock, app: FastAPI
    ) -> None:
        from backend.src.models.domain import QueryResult

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()
        mock_get_redis.return_value = mock_redis

        mock_execute.return_value = QueryResult(answer="fresh", source_nodes=[])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/v1/query", json={"query": "new query"})

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 3600  # ttl_seconds from RedisSettings default

    @patch("backend.src.api.query_routes.execute_query")
    @patch("backend.src.api.query_routes._get_redis_client")
    async def test_cache_key_uses_query_hash(
        self, mock_get_redis: MagicMock, mock_execute: MagicMock, app: FastAPI
    ) -> None:
        from backend.src.models.domain import QueryResult

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()
        mock_get_redis.return_value = mock_redis

        mock_execute.return_value = QueryResult(answer="ok", source_nodes=[])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/v1/query", json={"query": "hash test"})

        expected_key = "query:" + hashlib.sha256(b"hash test").hexdigest()
        mock_redis.get.assert_called_once_with(expected_key)


class TestSSEStreaming:
    @pytest.fixture
    def app(self) -> FastAPI:
        return _create_test_app()

    @patch("backend.src.api.query_routes._get_redis_client", return_value=None)
    @patch("backend.src.api.query_routes.execute_query")
    async def test_stream_returns_event_source_response(
        self, mock_execute: MagicMock, mock_redis: MagicMock, app: FastAPI
    ) -> None:
        from backend.src.models.domain import QueryResult, SourceNode

        mock_execute.return_value = QueryResult(
            answer="Streamed answer.",
            source_nodes=[SourceNode(text="src", score=0.9, metadata={})],
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/query", json={"query": "stream test", "stream": True})

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    @patch("backend.src.api.query_routes._get_redis_client", return_value=None)
    @patch("backend.src.api.query_routes.execute_query")
    async def test_stream_contains_answer_and_done_events(
        self, mock_execute: MagicMock, mock_redis: MagicMock, app: FastAPI
    ) -> None:
        from backend.src.models.domain import QueryResult, SourceNode

        mock_execute.return_value = QueryResult(
            answer="Full answer text.",
            source_nodes=[SourceNode(text="src", score=0.8, metadata={})],
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/query", json={"query": "stream events", "stream": True})

        body = resp.text
        assert "event: answer" in body
        assert "event: sources" in body
        assert "event: done" in body

    @patch("backend.src.api.query_routes._get_redis_client", return_value=None)
    @patch("backend.src.api.query_routes.execute_query")
    async def test_stream_cache_miss_still_executes_query(
        self, mock_execute: MagicMock, mock_redis: MagicMock, app: FastAPI
    ) -> None:
        """Streaming with cache miss still works; execute is called."""
        from backend.src.models.domain import QueryResult

        mock_execute.return_value = QueryResult(answer="ok", source_nodes=[])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/query", json={"query": "stream no cache", "stream": True})

        assert resp.status_code == 200
        mock_execute.assert_called_once()


class TestRateLimiting:
    @pytest.fixture
    def app(self) -> FastAPI:
        return _create_test_app()

    @patch("backend.src.api.query_routes._get_redis_client", return_value=None)
    @patch("backend.src.api.query_routes.execute_query")
    async def test_single_request_under_limit_succeeds(
        self, mock_execute: MagicMock, mock_redis: MagicMock, app: FastAPI
    ) -> None:
        from backend.src.models.domain import QueryResult

        mock_execute.return_value = QueryResult(answer="ok", source_nodes=[])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/query", json={"query": "rate test"})

        assert resp.status_code == 200

    @patch("backend.src.api.query_routes._get_redis_client", return_value=None)
    @patch("backend.src.api.query_routes.execute_query")
    async def test_exceeding_rate_limit_returns_429(
        self, mock_execute: MagicMock, mock_redis: MagicMock, app: FastAPI
    ) -> None:
        from backend.src.models.domain import QueryResult

        mock_execute.return_value = QueryResult(answer="ok", source_nodes=[])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            statuses = []
            for _ in range(25):
                resp = await client.post("/api/v1/query", json={"query": "rate test"})
                statuses.append(resp.status_code)

        assert 429 in statuses, f"Expected at least one 429 response, got: {set(statuses)}"
