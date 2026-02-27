"""Pydantic request and response schemas for the API."""

from __future__ import annotations

from pydantic import BaseModel


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
