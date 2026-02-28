"""Tests for collection and asset management API routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.api.main import create_app
from backend.src.core.config import Settings
from backend.src.models.tables import Base

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def _sqlite_session_factory() -> sessionmaker[Session]:
    """Create an in-memory SQLite engine with tables and return a sessionmaker."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture()
def _test_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("DEBUG", "true")
    return Settings(openai_api_key="sk-test")  # type: ignore[arg-type]


@pytest.fixture()
async def client(
    _test_settings: Settings,
    _sqlite_session_factory: sessionmaker[Session],
) -> AsyncClient:  # type: ignore[misc]
    """Async test client with dependency overrides for settings and DB session."""
    from backend.src.api.dependencies import get_session, get_settings

    app = create_app()

    app.dependency_overrides[get_settings] = lambda: _test_settings

    def _override_session() -> Generator[Session, None, None]:
        with _sqlite_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    app.state.session_factory = _sqlite_session_factory

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac  # type: ignore[misc]

    app.dependency_overrides.clear()


class TestCreateCollection:
    @pytest.mark.asyncio
    async def test_create_collection_returns_201(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/collections",
            json={"name": "leadership-docs", "description": "Core leadership documents"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "leadership-docs"
        assert data["description"] == "Core leadership documents"
        assert "id" in data
        assert "vector_table" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_collection_auto_generates_vector_table_name(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/collections",
            json={"name": "my-collection"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["vector_table"].startswith("vec_")

    @pytest.mark.asyncio
    async def test_create_collection_validates_empty_name(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/collections", json={"name": ""})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_duplicate_collection_returns_409(self, client: AsyncClient) -> None:
        await client.post("/api/v1/collections", json={"name": "unique-name"})
        response = await client.post("/api/v1/collections", json={"name": "unique-name"})
        assert response.status_code == 409


class TestListCollections:
    @pytest.mark.asyncio
    async def test_list_collections_empty(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/collections")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_collections_returns_created(self, client: AsyncClient) -> None:
        await client.post("/api/v1/collections", json={"name": "first"})
        await client.post("/api/v1/collections", json={"name": "second"})
        response = await client.get("/api/v1/collections")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        names = {c["name"] for c in data}
        assert names == {"first", "second"}

    @pytest.mark.asyncio
    async def test_list_collections_includes_asset_count(self, client: AsyncClient) -> None:
        await client.post("/api/v1/collections", json={"name": "with-assets"})
        response = await client.get("/api/v1/collections")
        data = response.json()
        assert data[0]["asset_count"] == 0


class TestGetCollection:
    @pytest.mark.asyncio
    async def test_get_collection_by_id(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/collections", json={"name": "target"})
        collection_id = resp.json()["id"]
        response = await client.get(f"/api/v1/collections/{collection_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "target"

    @pytest.mark.asyncio
    async def test_get_nonexistent_collection_returns_404(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/collections/nonexistent-id")
        assert response.status_code == 404


class TestListAssets:
    @pytest.mark.asyncio
    async def test_list_assets_empty(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/collections", json={"name": "empty-col"})
        collection_id = resp.json()["id"]
        response = await client.get(f"/api/v1/collections/{collection_id}/assets")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_assets_for_nonexistent_collection_returns_404(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/collections/bad-id/assets")
        assert response.status_code == 404


class TestUploadAssets:
    @pytest.mark.asyncio
    async def test_upload_asset_to_collection(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/collections", json={"name": "upload-test"})
        collection_id = resp.json()["id"]
        response = await client.post(
            f"/api/v1/collections/{collection_id}/assets",
            files=[("files", ("test.txt", b"hello world", "text/plain"))],
        )
        assert response.status_code == 202
        data = response.json()
        assert data["file_count"] == 1
        assert data["collection_id"] == collection_id

    @pytest.mark.asyncio
    async def test_upload_to_nonexistent_collection_returns_404(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/collections/bad-id/assets",
            files=[("files", ("test.txt", b"hello world", "text/plain"))],
        )
        assert response.status_code == 404


class TestCollectionSchemas:
    @pytest.mark.asyncio
    async def test_collection_response_schema(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/collections",
            json={"name": "schema-test", "description": "Testing schema"},
        )
        data = resp.json()
        expected_keys = {"id", "name", "description", "vector_table", "asset_count", "created_at", "updated_at"}
        assert set(data.keys()) == expected_keys
