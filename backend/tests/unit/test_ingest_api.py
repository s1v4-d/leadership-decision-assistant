"""Tests for the ingestion API endpoint."""

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.src.api.main import create_app
from backend.src.models.domain import IngestionResult

if TYPE_CHECKING:
    from fastapi import FastAPI


@pytest.fixture()
def app() -> FastAPI:
    return create_app()


@pytest.fixture()
async def client(app: FastAPI) -> httpx.AsyncClient:  # type: ignore[misc]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac  # type: ignore[misc]


def _make_upload_file(filename: str, content: bytes = b"test content") -> tuple[str, tuple[str, io.BytesIO]]:
    """Create a tuple suitable for httpx multipart file upload."""
    return ("files", (filename, io.BytesIO(content)))


class TestIngestEndpointReturns202:
    @patch("backend.src.api.ingest_routes._run_ingestion_task")
    async def test_ingest_returns_202_accepted(self, _mock_task: MagicMock, client: httpx.AsyncClient) -> None:
        files = [_make_upload_file("doc.txt")]
        response = await client.post("/api/v1/ingest", files=files)
        assert response.status_code == 202

    @patch("backend.src.api.ingest_routes._run_ingestion_task")
    async def test_ingest_returns_accepted_status_field(self, _mock_task: MagicMock, client: httpx.AsyncClient) -> None:
        files = [_make_upload_file("doc.txt")]
        response = await client.post("/api/v1/ingest", files=files)
        data = response.json()
        assert data["status"] == "accepted"

    @patch("backend.src.api.ingest_routes._run_ingestion_task")
    async def test_ingest_returns_file_count(self, _mock_task: MagicMock, client: httpx.AsyncClient) -> None:
        files = [_make_upload_file("a.txt"), _make_upload_file("b.md")]
        response = await client.post("/api/v1/ingest", files=files)
        data = response.json()
        assert data["file_count"] == 2

    @patch("backend.src.api.ingest_routes._run_ingestion_task")
    async def test_ingest_returns_message(self, _mock_task: MagicMock, client: httpx.AsyncClient) -> None:
        files = [_make_upload_file("doc.txt")]
        response = await client.post("/api/v1/ingest", files=files)
        data = response.json()
        assert "message" in data
        assert "1" in data["message"]


class TestIngestEndpointValidation:
    async def test_ingest_rejects_request_with_no_files(self, client: httpx.AsyncClient) -> None:
        response = await client.post("/api/v1/ingest")
        assert response.status_code == 422


class TestIngestEndpointBackgroundTask:
    @patch("backend.src.api.ingest_routes._run_ingestion_task")
    async def test_ingest_schedules_background_task(self, mock_task: MagicMock, client: httpx.AsyncClient) -> None:
        files = [_make_upload_file("doc.txt", b"hello world")]
        await client.post("/api/v1/ingest", files=files)
        mock_task.assert_called_once()

    @patch("backend.src.api.ingest_routes._run_ingestion_task")
    async def test_ingest_passes_directory_to_background_task(
        self, mock_task: MagicMock, client: httpx.AsyncClient
    ) -> None:
        files = [_make_upload_file("doc.txt")]
        await client.post("/api/v1/ingest", files=files)
        call_args = mock_task.call_args
        directory = call_args[0][0]
        assert isinstance(directory, Path)


class TestSaveUploadedFiles:
    async def test_saves_files_to_directory(self, tmp_path: Path) -> None:
        from backend.src.api.ingest_routes import _save_uploaded_files

        mock_file = MagicMock()
        mock_file.filename = "test.txt"
        mock_file.read = AsyncMock(return_value=b"file content")

        upload_dir = await _save_uploaded_files([mock_file], tmp_path)

        saved_file = upload_dir / "test.txt"
        assert saved_file.exists()
        assert saved_file.read_bytes() == b"file content"

    async def test_saves_multiple_files(self, tmp_path: Path) -> None:
        from backend.src.api.ingest_routes import _save_uploaded_files

        files = []
        for name in ["a.txt", "b.md"]:
            mock_file = MagicMock()
            mock_file.filename = name
            mock_file.read = AsyncMock(return_value=b"content")
            files.append(mock_file)

        upload_dir = await _save_uploaded_files(files, tmp_path)

        assert (upload_dir / "a.txt").exists()
        assert (upload_dir / "b.md").exists()

    async def test_skips_files_without_filename(self, tmp_path: Path) -> None:
        from backend.src.api.ingest_routes import _save_uploaded_files

        mock_file = MagicMock()
        mock_file.filename = None

        upload_dir = await _save_uploaded_files([mock_file], tmp_path)

        assert list(upload_dir.iterdir()) == []


class TestRunIngestionTask:
    @patch("backend.src.api.ingest_routes.ingest_documents")
    def test_calls_ingest_documents(self, mock_ingest: MagicMock, tmp_path: Path) -> None:
        from backend.src.api.ingest_routes import _run_ingestion_task
        from backend.src.core.config import Settings

        mock_ingest.return_value = IngestionResult(document_count=1, node_count=5, status="success")
        settings = Settings(_env_file=None, openai_api_key="sk-test")

        _run_ingestion_task(tmp_path, settings)

        mock_ingest.assert_called_once_with(tmp_path, settings)

    @patch("backend.src.api.ingest_routes.shutil.rmtree")
    @patch("backend.src.api.ingest_routes.ingest_documents")
    def test_cleans_up_temp_directory(self, mock_ingest: MagicMock, mock_rmtree: MagicMock, tmp_path: Path) -> None:
        from backend.src.api.ingest_routes import _run_ingestion_task
        from backend.src.core.config import Settings

        mock_ingest.return_value = IngestionResult(document_count=1, node_count=5, status="success")
        settings = Settings(_env_file=None, openai_api_key="sk-test")

        _run_ingestion_task(tmp_path, settings)

        mock_rmtree.assert_called_once_with(tmp_path, ignore_errors=True)

    @patch("backend.src.api.ingest_routes.shutil.rmtree")
    @patch("backend.src.api.ingest_routes.ingest_documents")
    def test_cleans_up_even_on_failure(self, mock_ingest: MagicMock, mock_rmtree: MagicMock, tmp_path: Path) -> None:
        from backend.src.api.ingest_routes import _run_ingestion_task
        from backend.src.core.config import Settings

        mock_ingest.side_effect = RuntimeError("pipeline error")
        settings = Settings(_env_file=None, openai_api_key="sk-test")

        _run_ingestion_task(tmp_path, settings)

        mock_rmtree.assert_called_once_with(tmp_path, ignore_errors=True)


class TestIngestEndpointMultipleFiles:
    @patch("backend.src.api.ingest_routes._run_ingestion_task")
    async def test_ingest_saves_uploaded_files_to_temp(self, mock_task: MagicMock, client: httpx.AsyncClient) -> None:
        files = [
            _make_upload_file("report.txt", b"report content"),
            _make_upload_file("notes.md", b"notes content"),
        ]
        response = await client.post("/api/v1/ingest", files=files)
        assert response.status_code == 202
        directory = mock_task.call_args[0][0]
        assert (directory / "report.txt").read_bytes() == b"report content"
        assert (directory / "notes.md").read_bytes() == b"notes content"
