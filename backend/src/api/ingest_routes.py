"""Ingestion API routes for document upload and processing."""

from __future__ import annotations

import shutil
import tempfile
from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, BackgroundTasks, UploadFile

from backend.src.api.dependencies import SettingsDep  # noqa: TC001
from backend.src.ingestion.pipeline import ingest_documents
from backend.src.models.schemas import IngestResponse

if TYPE_CHECKING:
    from pathlib import Path

    from backend.src.core.config import Settings

logger = structlog.get_logger(__name__)

ingest_router = APIRouter(prefix="/api/v1", tags=["ingestion"])


async def _save_uploaded_files(
    files: list[UploadFile],
    target_dir: Path | None = None,
) -> Path:
    """Save uploaded files to a directory, creating a temp dir if none provided."""
    if target_dir is None:
        target_dir = __import__("pathlib").Path(tempfile.mkdtemp())

    for file in files:
        if not file.filename:
            continue
        content = await file.read()
        (target_dir / file.filename).write_bytes(content)

    return target_dir


def _run_ingestion_task(directory: Path, settings: Settings) -> None:
    """Background task: run ingestion pipeline, then clean up temp files."""
    try:
        result = ingest_documents(directory, settings)
        logger.info(
            "background_ingestion_complete",
            status=result.status,
            document_count=result.document_count,
            node_count=result.node_count,
        )
    except Exception:
        logger.exception("background_ingestion_failed")
    finally:
        shutil.rmtree(directory, ignore_errors=True)


@ingest_router.post("/ingest", response_model=IngestResponse, status_code=202)
async def ingest_files(
    files: list[UploadFile],
    background_tasks: BackgroundTasks,
    settings: SettingsDep,
) -> IngestResponse:
    """Accept file uploads and start document ingestion in the background."""
    upload_dir = await _save_uploaded_files(files)
    background_tasks.add_task(_run_ingestion_task, upload_dir, settings)
    file_count = len([f for f in files if f.filename])
    logger.info("ingestion_accepted", file_count=file_count)
    return IngestResponse(
        status="accepted",
        message=f"Ingestion of {file_count} file(s) started",
        file_count=file_count,
    )
