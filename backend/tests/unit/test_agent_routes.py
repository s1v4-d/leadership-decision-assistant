"""Tests for the agent API routes."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.src.core.config import Settings
from backend.src.models.domain import AgentResponse
from backend.src.models.schemas import AgentQueryResponse


@pytest.fixture
def settings() -> Settings:
    return Settings(
        openai_api_key="sk-test",  # type: ignore[arg-type]
        debug=True,
    )


@pytest.fixture
def mock_agent() -> MagicMock:
    return MagicMock()


def _create_test_app(settings: Settings, agent: MagicMock) -> Any:
    """Create a test FastAPI app with mocked dependencies."""
    from fastapi import FastAPI

    from backend.src.api.agent_routes import agent_router, get_leadership_agent
    from backend.src.core.config import get_settings

    app = FastAPI()
    app.include_router(agent_router)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_leadership_agent] = lambda: agent
    return app


class TestAgentQueryEndpoint:
    @pytest.mark.asyncio
    async def test_agent_query_returns_response(self, settings: Settings, mock_agent: MagicMock) -> None:
        app = _create_test_app(settings, mock_agent)

        agent_response = AgentResponse(answer="Revenue grew 15% in Q4.", tool_calls_count=1)
        with patch(
            "backend.src.api.agent_routes.run_agent_query",
            new_callable=AsyncMock,
            return_value=agent_response,
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/v1/agent", json={"query": "What is Q4 revenue?"})

        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["answer"] == "Revenue grew 15% in Q4."
        assert data["tool_calls_count"] == 1

    @pytest.mark.asyncio
    async def test_agent_query_with_stream_false(self, settings: Settings, mock_agent: MagicMock) -> None:
        app = _create_test_app(settings, mock_agent)

        agent_response = AgentResponse(answer="Some answer.", tool_calls_count=0)
        with patch(
            "backend.src.api.agent_routes.run_agent_query",
            new_callable=AsyncMock,
            return_value=agent_response,
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/v1/agent", json={"query": "Hello", "stream": False})

        assert resp.status_code == 200
        assert resp.json()["answer"] == "Some answer."

    @pytest.mark.asyncio
    async def test_agent_query_validates_empty_query(self, settings: Settings, mock_agent: MagicMock) -> None:
        app = _create_test_app(settings, mock_agent)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/agent", json={"query": ""})

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_agent_query_stream_returns_sse(self, settings: Settings, mock_agent: MagicMock) -> None:
        app = _create_test_app(settings, mock_agent)

        async def fake_stream(*args: Any, **kwargs: Any) -> Any:
            yield "token1"
            yield " token2"

        with patch(
            "backend.src.api.agent_routes.stream_agent_response",
            return_value=fake_stream(),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/v1/agent", json={"query": "test", "stream": True})

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_agent_query_sanitizes_input(self, settings: Settings, mock_agent: MagicMock) -> None:
        app = _create_test_app(settings, mock_agent)

        agent_response = AgentResponse(answer="Safe answer.", tool_calls_count=0)
        with patch(
            "backend.src.api.agent_routes.run_agent_query",
            new_callable=AsyncMock,
            return_value=agent_response,
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/v1/agent", json={"query": "  hello  world  "})

        assert resp.status_code == 200


class TestAgentQueryResponseSchema:
    def test_agent_query_response_schema(self) -> None:
        resp = AgentQueryResponse(answer="test", tool_calls_count=2)
        assert resp.answer == "test"
        assert resp.tool_calls_count == 2

    def test_agent_query_response_defaults(self) -> None:
        resp = AgentQueryResponse(answer="test")
        assert resp.tool_calls_count == 0
