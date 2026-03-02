"""HTTP client for the Leadership Decision Assistant backend API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from collections.abc import Generator

_HTTP_OK = 200


def check_health(base_url: str) -> bool:
    """Check if the backend API is healthy."""
    try:
        response = httpx.get(f"{base_url}/health", timeout=5.0)
        return response.status_code == _HTTP_OK
    except httpx.HTTPError:
        return False


def query_documents(base_url: str, query: str) -> dict[str, Any]:
    """Send a non-streaming query to the backend API."""
    response = httpx.post(
        f"{base_url}/api/v1/query",
        json={"query": query, "stream": False},
        timeout=120.0,
    )
    response.raise_for_status()
    result: dict[str, Any] = response.json()
    return result


def parse_sse_events(text: str) -> Generator[tuple[str, str], None, None]:
    """Parse SSE text into (event_type, data) tuples."""
    event_type = ""
    data = ""

    for raw_line in text.split("\n"):
        line = raw_line.strip("\r")
        if line.startswith(":"):
            continue
        if line.startswith("event: "):
            event_type = line[7:]
        elif line.startswith("data: "):
            data = line[6:]
        elif line == "" and event_type:
            yield event_type, data
            event_type = ""
            data = ""


def query_documents_stream(base_url: str, query: str) -> Generator[tuple[str, str], None, None]:
    """Send a streaming query and yield SSE events."""
    with httpx.stream(
        "POST",
        f"{base_url}/api/v1/query",
        json={"query": query, "stream": True},
        timeout=120.0,
    ) as response:
        for chunk in response.iter_text():
            yield from parse_sse_events(chunk)


def ingest_documents(base_url: str, files: list[Any]) -> dict[str, Any]:
    """Upload files to the backend ingestion endpoint."""
    multipart_files = [("files", (f.name, f.getvalue())) for f in files]
    response = httpx.post(
        f"{base_url}/api/v1/ingest",
        files=multipart_files,
        timeout=120.0,
    )
    response.raise_for_status()
    ingest_result: dict[str, Any] = response.json()
    return ingest_result


def query_agent(base_url: str, query: str) -> dict[str, Any]:
    """Send a non-streaming query to the agent endpoint."""
    response = httpx.post(
        f"{base_url}/api/v1/agent",
        json={"query": query, "stream": False},
        timeout=120.0,
    )
    response.raise_for_status()
    result: dict[str, Any] = response.json()
    return result


def query_agent_stream(base_url: str, query: str) -> Generator[tuple[str, str], None, None]:
    """Send a streaming query to the agent endpoint and yield SSE events."""
    with httpx.stream(
        "POST",
        f"{base_url}/api/v1/agent",
        json={"query": query, "stream": True},
        timeout=120.0,
    ) as response:
        for chunk in response.iter_text():
            yield from parse_sse_events(chunk)
