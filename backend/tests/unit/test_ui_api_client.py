"""Tests for the UI API client module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from ui.api_client import (
    check_health,
    ingest_documents,
    parse_sse_events,
    query_documents,
    query_documents_stream,
)


class TestCheckHealth:
    @patch("ui.api_client.httpx.get")
    def test_returns_true_when_healthy(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"status": "ok"}),
        )

        result = check_health("http://localhost:8000")

        assert result is True
        mock_get.assert_called_once_with("http://localhost:8000/health", timeout=5.0)

    @patch("ui.api_client.httpx.get")
    def test_returns_false_on_connection_error(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = httpx.ConnectError("Connection refused")

        result = check_health("http://localhost:8000")

        assert result is False

    @patch("ui.api_client.httpx.get")
    def test_returns_false_on_non_200(self, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock(status_code=503)

        result = check_health("http://localhost:8000")

        assert result is False


class TestQueryDocuments:
    @patch("ui.api_client.httpx.post")
    def test_returns_query_response(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(
                return_value={
                    "answer": "The answer is 42",
                    "sources": [{"text": "source1", "score": 0.9, "metadata": {}}],
                    "cached": False,
                }
            ),
            raise_for_status=MagicMock(),
        )

        result = query_documents("http://localhost:8000", "What is the answer?")

        assert result["answer"] == "The answer is 42"
        assert len(result["sources"]) == 1
        mock_post.assert_called_once_with(
            "http://localhost:8000/api/v1/query",
            json={"query": "What is the answer?", "stream": False},
            timeout=120.0,
        )

    @patch("ui.api_client.httpx.post")
    def test_raises_on_http_error(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock(status_code=429)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Rate limited", request=MagicMock(), response=mock_response
        )
        mock_post.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            query_documents("http://localhost:8000", "test")


class TestParseSseEvents:
    def test_parses_answer_event(self) -> None:
        lines = "event: answer\ndata: The answer is 42\n\n"
        events = list(parse_sse_events(lines))

        assert events == [("answer", "The answer is 42")]

    def test_parses_multiple_events(self) -> None:
        lines = 'event: answer\ndata: Hello\n\nevent: sources\ndata: [{"text": "src"}]\n\nevent: done\ndata: \n\n'
        events = list(parse_sse_events(lines))

        assert len(events) == 3
        assert events[0] == ("answer", "Hello")
        assert events[1] == ("sources", '[{"text": "src"}]')
        assert events[2] == ("done", "")

    def test_handles_empty_input(self) -> None:
        events = list(parse_sse_events(""))
        assert events == []

    def test_ignores_comment_lines(self) -> None:
        lines = ": keep-alive\nevent: answer\ndata: test\n\n"
        events = list(parse_sse_events(lines))

        assert events == [("answer", "test")]


class TestQueryDocumentsStream:
    @patch("ui.api_client.httpx.stream")
    def test_yields_sse_events(self, mock_stream: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.status_code = 200
        mock_response.iter_text.return_value = iter(["event: answer\ndata: Hello\n\n", "event: done\ndata: \n\n"])
        mock_stream.return_value = mock_response

        events = list(query_documents_stream("http://localhost:8000", "test query"))

        assert ("answer", "Hello") in events
        assert ("done", "") in events
        mock_stream.assert_called_once_with(
            "POST",
            "http://localhost:8000/api/v1/query",
            json={"query": "test query", "stream": True},
            timeout=120.0,
        )


class TestIngestDocuments:
    @patch("ui.api_client.httpx.post")
    def test_returns_ingest_response(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            status_code=202,
            json=MagicMock(
                return_value={
                    "status": "accepted",
                    "message": "Ingestion of 2 file(s) started",
                    "file_count": 2,
                }
            ),
            raise_for_status=MagicMock(),
        )

        file1 = MagicMock()
        file1.name = "report.pdf"
        file1.getvalue.return_value = b"pdf content"
        file2 = MagicMock()
        file2.name = "notes.txt"
        file2.getvalue.return_value = b"text content"

        result = ingest_documents("http://localhost:8000", [file1, file2])

        assert result["file_count"] == 2
        assert result["status"] == "accepted"

    @patch("ui.api_client.httpx.post")
    def test_raises_on_error(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock(status_code=422)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Validation error", request=MagicMock(), response=mock_response
        )
        mock_post.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            ingest_documents("http://localhost:8000", [MagicMock()])
