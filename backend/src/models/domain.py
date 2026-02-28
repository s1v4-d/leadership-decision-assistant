"""Domain models for internal business logic."""

from __future__ import annotations

from pydantic import BaseModel


class IngestionResult(BaseModel):
    """Result of a document ingestion operation."""

    document_count: int
    node_count: int
    status: str
    error_message: str | None = None


class SourceNode(BaseModel):
    """A retrieved source chunk with relevance score."""

    text: str
    score: float
    metadata: dict[str, str] = {}


class QueryResult(BaseModel):
    """Result of a RAG query execution."""

    answer: str
    source_nodes: list[SourceNode]
    confidence_score: float | None = None


class AgentResponse(BaseModel):
    """Result of a leadership agent query."""

    answer: str
    tool_calls_count: int = 0
