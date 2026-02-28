"""Startup seed logic — auto-ingest sample documents if vector store is empty."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import MetaData, Table, inspect, select

from backend.src.ingestion.pipeline import create_vector_store, ingest_documents

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

    from backend.src.core.config import Settings

logger = structlog.get_logger(__name__)

_SAMPLE_DOCS_DIR = Path(__file__).resolve().parents[3] / "data" / "sample_documents"


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
