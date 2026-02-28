"""Startup seed logic — auto-ingest sample documents and structured data."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import MetaData, Table, func, inspect, select

from backend.src.ingestion.excel_parser import ingest_excel_to_business_metrics
from backend.src.ingestion.pipeline import create_vector_store, ingest_documents
from backend.src.models.tables import BusinessMetric, Collection

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session

    from backend.src.core.config import Settings

logger = structlog.get_logger(__name__)

_SAMPLE_DOCS_DIR = Path(__file__).resolve().parents[3] / "data" / "sample_documents"
_DEFAULT_COLLECTION_NAME = "leadership"
_DEFAULT_VECTOR_TABLE = "vec_leadership_default"


def _table_has_rows(engine: Engine, table_name: str) -> bool:
    """Check if the given table has at least one row."""
    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)
    with engine.connect() as conn:
        result = conn.execute(select(table).limit(1)).first()
        return result is not None


def _vector_store_has_data(settings: Settings) -> bool:
    """Return True if the pgvector table exists and contains rows."""
    store = create_vector_store(settings)
    engine = store._engine  # noqa: SLF001
    if engine is None:
        return False
    inspector = inspect(engine)
    if store.table_name not in inspector.get_table_names():  # type: ignore[union-attr]
        return False
    return _table_has_rows(engine, store.table_name)


def _ensure_default_collection(session: Session) -> Collection:
    """Create the default 'leadership' collection if it doesn't exist."""
    existing = session.execute(
        select(Collection).where(Collection.name == _DEFAULT_COLLECTION_NAME)
    ).scalar_one_or_none()
    if existing:
        logger.info("default_collection_exists", collection_id=existing.id)
        return existing

    collection = Collection(
        name=_DEFAULT_COLLECTION_NAME,
        description="Default leadership decision support collection",
        vector_table=_DEFAULT_VECTOR_TABLE,
    )
    session.add(collection)
    session.commit()
    session.refresh(collection)
    logger.info("default_collection_created", collection_id=collection.id)
    return collection


def _business_metrics_has_data(session: Session) -> bool:
    """Return True if the business_metrics table has at least one row."""
    count = session.execute(select(func.count(BusinessMetric.id))).scalar_one_or_none()
    return bool(count and count > 0)


def _find_excel_files(directory: Path) -> list[Path]:
    """Find all .xlsx files in the sample documents directory."""
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.xlsx"))


def seed_sample_documents(settings: Settings) -> None:
    """Ingest sample documents if the vector store is empty."""
    try:
        has_data = _vector_store_has_data(settings)
    except Exception:
        logger.exception("seed_check_failed")
        return

    if has_data:
        logger.info("seed_skipped", reason="vector store already has data")
        return

    if not _SAMPLE_DOCS_DIR.is_dir():
        logger.warning("seed_skipped", reason="sample docs directory not found", path=str(_SAMPLE_DOCS_DIR))
        return

    try:
        result = ingest_documents(_SAMPLE_DOCS_DIR, settings)
        logger.info(
            "seed_complete",
            status=result.status,
            documents=result.document_count,
            nodes=result.node_count,
        )
    except Exception:
        logger.exception("seed_ingestion_failed")


def seed_business_metrics(session: Session, collection_id: str) -> None:
    """Ingest Excel data into business_metrics table if empty."""
    if _business_metrics_has_data(session):
        logger.info("seed_metrics_skipped", reason="business_metrics already has data")
        return

    excel_files = _find_excel_files(_SAMPLE_DOCS_DIR)
    if not excel_files:
        logger.info("seed_metrics_skipped", reason="no Excel files found")
        return

    for filepath in excel_files:
        try:
            count = ingest_excel_to_business_metrics(filepath, session, collection_id)
            logger.info("seed_metrics_complete", filepath=str(filepath), rows=count)
        except Exception:
            logger.exception("seed_metrics_failed", filepath=str(filepath))
