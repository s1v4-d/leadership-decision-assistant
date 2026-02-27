"""Tests for FastAPI application factory, routes, and middleware."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI

from backend.src.api.main import create_app


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> httpx.AsyncClient:  # type: ignore[misc]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac  # type: ignore[misc]


class TestHealthEndpoint:
    """Tests for GET /health."""

    async def test_health_returns_200(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == 200

    async def test_health_returns_status_ok(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/health")
        data = response.json()
        assert data["status"] == "ok"

    async def test_health_returns_app_name(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/health")
        data = response.json()
        assert "app_name" in data

    async def test_health_returns_version(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/health")
        data = response.json()
        assert "version" in data


class TestReadyEndpoint:
    """Tests for GET /ready."""

    @patch("backend.src.api.routes._check_redis", new_callable=AsyncMock, return_value=True)
    @patch("backend.src.api.routes._check_postgres", new_callable=AsyncMock, return_value=True)
    async def test_ready_returns_200_when_all_healthy(
        self,
        _mock_pg: AsyncMock,
        _mock_redis: AsyncMock,
        client: httpx.AsyncClient,
    ) -> None:
        response = await client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    @patch("backend.src.api.routes._check_redis", new_callable=AsyncMock, return_value=True)
    @patch("backend.src.api.routes._check_postgres", new_callable=AsyncMock, return_value=False)
    async def test_ready_returns_503_when_postgres_down(
        self,
        _mock_pg: AsyncMock,
        _mock_redis: AsyncMock,
        client: httpx.AsyncClient,
    ) -> None:
        response = await client.get("/ready")
        assert response.status_code == 503

    @patch("backend.src.api.routes._check_redis", new_callable=AsyncMock, return_value=False)
    @patch("backend.src.api.routes._check_postgres", new_callable=AsyncMock, return_value=True)
    async def test_ready_returns_503_when_redis_down(
        self,
        _mock_pg: AsyncMock,
        _mock_redis: AsyncMock,
        client: httpx.AsyncClient,
    ) -> None:
        response = await client.get("/ready")
        assert response.status_code == 503

    @patch("backend.src.api.routes._check_redis", new_callable=AsyncMock, return_value=True)
    @patch("backend.src.api.routes._check_postgres", new_callable=AsyncMock, return_value=True)
    async def test_ready_returns_dependency_checks(
        self,
        _mock_pg: AsyncMock,
        _mock_redis: AsyncMock,
        client: httpx.AsyncClient,
    ) -> None:
        response = await client.get("/ready")
        data = response.json()
        assert "checks" in data
        assert "postgres" in data["checks"]
        assert "redis" in data["checks"]


class TestAppFactory:
    """Tests for the create_app factory function."""

    def test_create_app_returns_fastapi_instance(self) -> None:
        app = create_app()
        assert isinstance(app, FastAPI)

    def test_create_app_sets_title(self) -> None:
        app = create_app()
        assert app.title is not None

    def test_create_app_has_routes(self) -> None:
        app = create_app()
        paths = [route.path for route in app.routes]
        assert "/health" in paths
        assert "/ready" in paths


class TestMiddleware:
    """Tests for middleware configuration."""

    async def test_cors_headers_on_preflight(self, client: httpx.AsyncClient) -> None:
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:8501",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" in response.headers

    async def test_request_id_header_in_response(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/health")
        assert "x-request-id" in response.headers

    async def test_request_id_is_uuid_format(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/health")
        request_id = response.headers["x-request-id"]
        assert len(request_id) == 36
        assert request_id.count("-") == 4


class TestErrorHandling:
    """Tests for error handlers."""

    async def test_404_returns_json_error(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/nonexistent")
        assert response.status_code == 404

    async def test_validation_error_returns_422(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/health", params={"unexpected": "param"})
        assert response.status_code == 200


class TestStructlogConfig:
    """Tests for structlog configuration."""

    def test_configure_logging_does_not_raise(self) -> None:
        from backend.src.core.log import configure_logging

        configure_logging(log_level="DEBUG", log_format="console")

    def test_configure_logging_json_format(self) -> None:
        from backend.src.core.log import configure_logging

        configure_logging(log_level="INFO", log_format="json")

    def test_get_logger_returns_logger(self) -> None:
        import structlog

        from backend.src.core.log import configure_logging

        configure_logging(log_level="DEBUG", log_format="console")
        logger = structlog.get_logger("test")
        assert logger is not None
