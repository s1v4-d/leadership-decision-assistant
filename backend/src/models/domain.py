"""Domain models for internal business logic."""

from __future__ import annotations

from pydantic import BaseModel


class IngestionResult(BaseModel):
    """Result of a document ingestion operation."""

    document_count: int
    node_count: int
    status: str
    error_message: str | None = None
