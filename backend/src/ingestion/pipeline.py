"""Document ingestion pipeline orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from llama_index.core.ingestion import IngestionPipeline
from llama_index.vector_stores.postgres import PGVectorStore

from backend.src.core.llm_provider import create_embed_model
from backend.src.ingestion.chunking import create_sentence_splitter
from backend.src.ingestion.parsers import load_documents
from backend.src.models.domain import IngestionResult

if TYPE_CHECKING:
    from pathlib import Path

    from backend.src.core.config import Settings

logger = structlog.get_logger(__name__)

_HNSW_DEFAULTS = {
    "hnsw_m": 16,
    "hnsw_ef_construction": 64,
    "hnsw_ef_search": 40,
    "hnsw_dist_method": "vector_cosine_ops",
}


def create_vector_store(settings: Settings, *, table_name: str | None = None) -> PGVectorStore:
    """Create a PGVectorStore, optionally targeting a specific collection table."""
    pg = settings.postgres
    return PGVectorStore.from_params(
        database=pg.database,
        host=pg.host,
        password=pg.password.get_secret_value(),
        port=str(pg.port),
        user=pg.user,
        table_name=table_name or pg.vector_table,
        embed_dim=settings.embedding_dimension,
        hnsw_kwargs=_HNSW_DEFAULTS,
    )


def create_ingestion_pipeline(settings: Settings, *, table_name: str | None = None) -> IngestionPipeline:
    """Assemble a LlamaIndex IngestionPipeline with chunking, embedding, and vector storage."""
    vector_store = create_vector_store(settings, table_name=table_name)
    splitter = create_sentence_splitter(settings.rag)

    return IngestionPipeline(
        transformations=[
            splitter,
            create_embed_model(settings),
        ],
        vector_store=vector_store,
    )


def ingest_documents(directory: Path, settings: Settings, *, table_name: str | None = None) -> IngestionResult:
    """Load documents from directory, run through ingestion pipeline, and store vectors."""
    try:
        documents = load_documents(directory)
        pipeline = create_ingestion_pipeline(settings, table_name=table_name)
        nodes = pipeline.run(documents=documents)
        logger.info(
            "ingestion_complete",
            document_count=len(documents),
            node_count=len(nodes),
        )
        return IngestionResult(
            document_count=len(documents),
            node_count=len(nodes),
            status="success",
        )
    except Exception as exc:
        logger.exception("ingestion_failed", error=str(exc))
        return IngestionResult(
            document_count=0,
            node_count=0,
            status="failed",
            error_message=str(exc),
        )
