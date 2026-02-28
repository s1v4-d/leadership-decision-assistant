"""RAG query engine tool for document-grounded retrieval."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from llama_index.core import VectorStoreIndex
from llama_index.core.vector_stores import (
    FilterCondition,
    MetadataFilter,
    MetadataFilters,
)

from backend.src.ingestion.pipeline import create_vector_store
from backend.src.models.domain import QueryResult, SourceNode

if TYPE_CHECKING:
    from llama_index.core.base.base_query_engine import BaseQueryEngine

    from backend.src.core.config import Settings

logger = structlog.get_logger(__name__)


def _build_metadata_filters(
    *,
    collection_id: str | None = None,
) -> MetadataFilters | None:
    """Build LlamaIndex MetadataFilters for scoped retrieval."""
    filters: list[MetadataFilter | MetadataFilters] = []
    if collection_id:
        filters.append(MetadataFilter(key="collection_id", value=collection_id))
    if not filters:
        return None
    return MetadataFilters(filters=filters, condition=FilterCondition.AND)


def create_query_index(settings: Settings, *, table_name: str | None = None) -> VectorStoreIndex:
    """Build a VectorStoreIndex from the existing pgvector store."""
    vector_store = create_vector_store(settings, table_name=table_name)
    return VectorStoreIndex.from_vector_store(vector_store=vector_store)


def create_query_engine(
    settings: Settings,
    *,
    table_name: str | None = None,
    collection_id: str | None = None,
) -> BaseQueryEngine:
    """Create a query engine with configured RAG settings.

    When *collection_id* is supplied the retriever will apply a
    ``MetadataFilter`` so only chunks tagged with that collection are
    returned — mirroring the asset-based filtering pattern from talk2data.
    """
    index = create_query_index(settings, table_name=table_name)
    metadata_filters = _build_metadata_filters(collection_id=collection_id)

    kwargs: dict[str, object] = {
        "similarity_top_k": settings.rag.similarity_top_k,
        "response_mode": settings.rag.response_mode,
    }
    if metadata_filters is not None:
        kwargs["filters"] = metadata_filters

    return index.as_query_engine(**kwargs)


def execute_query(
    query_text: str,
    settings: Settings,
    *,
    table_name: str | None = None,
    collection_id: str | None = None,
) -> QueryResult:
    """Run a RAG query and return structured results with source nodes."""
    try:
        engine = create_query_engine(
            settings,
            table_name=table_name,
            collection_id=collection_id,
        )
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
            collection_id=collection_id,
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
