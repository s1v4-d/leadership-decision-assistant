"""Pydantic request and response schemas for the API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response schema for GET /health."""

    status: str
    app_name: str
    version: str


class ReadyResponse(BaseModel):
    """Response schema for GET /ready."""

    status: str
    checks: dict[str, bool]


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    error: str
    detail: str | None = None
    request_id: str | None = None


class IngestResponse(BaseModel):
    """Response schema for POST /api/v1/ingest."""

    status: str
    message: str
    file_count: int


class SourceNodeResponse(BaseModel):
    """A single source chunk returned by a query."""

    text: str
    score: float
    metadata: dict[str, str] = {}


class QueryRequest(BaseModel):
    """Request schema for POST /api/v1/query."""

    query: str = Field(min_length=1, max_length=2000)
    stream: bool = False


class QueryResponse(BaseModel):
    """Response schema for POST /api/v1/query."""

    answer: str
    sources: list[SourceNodeResponse] = []
    cached: bool = False


class AgentRequest(BaseModel):
    """Request schema for POST /api/v1/agent."""

    query: str = Field(min_length=1, max_length=2000)
    stream: bool = False


class AgentQueryResponse(BaseModel):
    """Response schema for POST /api/v1/agent."""

    answer: str
    tool_calls_count: int = 0
