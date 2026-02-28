"""Collection and asset management API routes."""

from __future__ import annotations

import re
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from sqlalchemy import func, select

from backend.src.api.dependencies import SessionDep, SettingsDep  # noqa: TC001
from backend.src.ingestion.pipeline import ingest_documents
from backend.src.models.schemas import AssetUploadResponse, CollectionCreate, CollectionResponse
from backend.src.models.tables import Asset, Collection

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

    return _to_collection_response(collection, asset_count=0)


@collection_router.get("/collections", response_model=list[CollectionResponse])
def list_collections(session: SessionDep) -> list[CollectionResponse]:
    """List all collections with asset counts."""
    stmt = (
        select(Collection, func.count(Asset.id).label("asset_count"))
        .outerjoin(Asset, Asset.collection_id == Collection.id)
        .group_by(Collection.id)
    )
    results = session.execute(stmt).all()
    return [_to_collection_response(row[0], asset_count=row[1]) for row in results]


@collection_router.get("/collections/{collection_id}", response_model=CollectionResponse)
def get_collection(collection_id: str, session: SessionDep) -> CollectionResponse:
    """Get a single collection by ID."""
    collection = session.get(Collection, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    asset_count = session.scalar(select(func.count(Asset.id)).where(Asset.collection_id == collection_id)) or 0
    return _to_collection_response(collection, asset_count=asset_count)


@collection_router.get("/collections/{collection_id}/assets")
def list_assets(collection_id: str, session: SessionDep) -> list[dict[str, str]]:
    """List assets in a collection."""
    collection = session.get(Collection, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    assets = session.execute(select(Asset).where(Asset.collection_id == collection_id)).scalars().all()
    return [
        {
            "id": a.id,
            "filename": a.filename,
            "file_type": a.file_type,
            "created_at": str(a.created_at),
        }
        for a in assets
    ]


@collection_router.post("/collections/{collection_id}/assets", response_model=AssetUploadResponse, status_code=202)
async def upload_assets(
    collection_id: str,
    files: list[UploadFile],
    background_tasks: BackgroundTasks,
    session: SessionDep,
    settings: SettingsDep,
) -> AssetUploadResponse:
    """Upload files into a specific collection."""
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
        suffix = Path(file.filename).suffix.lstrip(".")
        asset = Asset(collection_id=collection_id, filename=file.filename, file_type=suffix or "unknown")
        session.add(asset)
        file_count += 1

    session.commit()
    background_tasks.add_task(_run_collection_ingestion, upload_dir, settings)

    logger.info("collection_upload_accepted", collection_id=collection_id, file_count=file_count)
    return AssetUploadResponse(status="accepted", collection_id=collection_id, file_count=file_count)


def _run_collection_ingestion(directory: Path, settings: Settings) -> None:
    """Background task: ingest uploaded files, then clean up."""
    try:
        result = ingest_documents(directory, settings)
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


def _to_collection_response(collection: Collection, *, asset_count: int) -> CollectionResponse:
    """Map an ORM Collection to CollectionResponse."""
    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        vector_table=collection.vector_table,
        asset_count=asset_count,
        created_at=str(collection.created_at),
        updated_at=str(collection.updated_at),
    )
