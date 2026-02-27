"""RAG query engine tool for document-grounded retrieval."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from llama_index.core import VectorStoreIndex

from backend.src.ingestion.pipeline import create_vector_store
from backend.src.models.domain import QueryResult, SourceNode

if TYPE_CHECKING:
    from llama_index.core.base.base_query_engine import BaseQueryEngine

    from backend.src.core.config import Settings

logger = structlog.get_logger(__name__)


def create_query_index(settings: Settings) -> VectorStoreIndex:
    """Build a VectorStoreIndex from the existing pgvector store."""
    vector_store = create_vector_store(settings)
    return VectorStoreIndex.from_vector_store(vector_store=vector_store)


def create_query_engine(settings: Settings) -> BaseQueryEngine:
    """Create a query engine with configured RAG settings."""
    index = create_query_index(settings)
    return index.as_query_engine(
        similarity_top_k=settings.rag.similarity_top_k,
        response_mode=settings.rag.response_mode,
    )


def execute_query(query_text: str, settings: Settings) -> QueryResult:
    """Run a RAG query and return structured results with source nodes."""
    try:
        engine = create_query_engine(settings)
        response = engine.query(query_text)

        source_nodes = [
            SourceNode(
                text=node.node.get_content(),
                score=node.score if node.score is not None else 0.0,
                metadata=node.node.metadata,
            )
            for node in response.source_nodes
        ]

        logger.info(
            "query_executed",
            query_length=len(query_text),
            source_count=len(source_nodes),
        )

        answer = str(response) if response else ""
        return QueryResult(
            answer=answer,
            source_nodes=source_nodes,
        )
    except Exception as exc:
        logger.exception("query_failed", error=str(exc))
        return QueryResult(
            answer=f"Query failed: {exc}",
            source_nodes=[],
        )
