"""Collection management API routes.

Assets are stored as document metadata (filename, collection_id, file_type)
inside the pgvector table — not as a separate SQL table. This mirrors the
talk2data pattern where asset_id is a JSONB metadata field used for filtering.
"""

from __future__ import annotations

import re
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from sqlalchemy import select

from backend.src.api.dependencies import SessionDep, SettingsDep  # noqa: TC001
from backend.src.ingestion.pipeline import ingest_documents
from backend.src.models.schemas import AssetUploadResponse, CollectionCreate, CollectionResponse
from backend.src.models.tables import Collection

if TYPE_CHECKING:
    from backend.src.core.config import Settings

logger = structlog.get_logger(__name__)

collection_router = APIRouter(prefix="/api/v1", tags=["collections"])


def _generate_vector_table_name(collection_name: str) -> str:
    """Generate a vector table name from a collection name."""
    slug = re.sub(r"[^a-z0-9]+", "_", collection_name.lower()).strip("_")
    short_id = uuid.uuid4().hex[:8]
    return f"vec_{slug}_{short_id}"


@collection_router.post("/collections", response_model=CollectionResponse, status_code=201)
def create_collection(body: CollectionCreate, session: SessionDep) -> CollectionResponse:
    """Create a new document collection."""
    existing = session.execute(select(Collection).where(Collection.name == body.name)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Collection '{body.name}' already exists")

    collection = Collection(
        name=body.name,
        description=body.description,
        vector_table=_generate_vector_table_name(body.name),
    )
    session.add(collection)
    session.commit()
    session.refresh(collection)

    logger.info("collection_created", collection_id=collection.id, name=collection.name)

    return _to_collection_response(collection)


@collection_router.get("/collections", response_model=list[CollectionResponse])
def list_collections(session: SessionDep) -> list[CollectionResponse]:
    """List all collections."""
    results = session.execute(select(Collection)).scalars().all()
    return [_to_collection_response(c) for c in results]


@collection_router.get("/collections/{collection_id}", response_model=CollectionResponse)
def get_collection(collection_id: str, session: SessionDep) -> CollectionResponse:
    """Get a single collection by ID."""
    collection = session.get(Collection, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    return _to_collection_response(collection)


@collection_router.post("/collections/{collection_id}/assets", response_model=AssetUploadResponse, status_code=202)
async def upload_assets(
    collection_id: str,
    files: list[UploadFile],
    background_tasks: BackgroundTasks,
    session: SessionDep,
    settings: SettingsDep,
) -> AssetUploadResponse:
    """Upload files into a collection.

    File metadata (filename, file_type, collection_id) is injected into each
    document's metadata during ingestion — no separate assets table needed.
    """
    collection = session.get(Collection, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    upload_dir = Path(tempfile.mkdtemp())
    file_count = 0
    for file in files:
        if not file.filename:
            continue
        content = await file.read()
        (upload_dir / file.filename).write_bytes(content)
        file_count += 1

    extra_metadata = {"collection_id": collection_id}
    background_tasks.add_task(
        _run_collection_ingestion,
        upload_dir,
        settings,
        collection.vector_table,
        extra_metadata,
    )

    logger.info("collection_upload_accepted", collection_id=collection_id, file_count=file_count)
    return AssetUploadResponse(status="accepted", collection_id=collection_id, file_count=file_count)


def _run_collection_ingestion(
    directory: Path,
    settings: Settings,
    vector_table: str,
    extra_metadata: dict[str, str],
) -> None:
    """Background task: ingest uploaded files into a collection's vector table."""
    try:
        result = ingest_documents(
            directory,
            settings,
            table_name=vector_table,
            extra_metadata=extra_metadata,
        )
        logger.info(
            "collection_ingestion_complete",
            status=result.status,
            document_count=result.document_count,
            node_count=result.node_count,
        )
    except Exception:
        logger.exception("collection_ingestion_failed")
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def _to_collection_response(collection: Collection) -> CollectionResponse:
    """Map an ORM Collection to CollectionResponse."""
    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        vector_table=collection.vector_table,
        created_at=str(collection.created_at),
        updated_at=str(collection.updated_at),
    )
