"""Tests for RAG query engine and vector search."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.src.core.config import RAGSettings, Settings


class TestQueryResult:
    def test_query_result_has_required_fields(self) -> None:
        from backend.src.models.domain import QueryResult

        result = QueryResult(
            answer="Test answer",
            source_nodes=[],
            confidence_score=0.95,
        )
        assert result.answer == "Test answer"
        assert result.source_nodes == []
        assert result.confidence_score == 0.95

    def test_query_result_default_confidence_is_none(self) -> None:
        from backend.src.models.domain import QueryResult

        result = QueryResult(answer="Test", source_nodes=[])
        assert result.confidence_score is None

    def test_source_node_has_required_fields(self) -> None:
        from backend.src.models.domain import SourceNode

        node = SourceNode(
            text="Some text",
            score=0.87,
            metadata={"file": "doc.pdf"},
        )
        assert node.text == "Some text"
        assert node.score == 0.87
        assert node.metadata == {"file": "doc.pdf"}

    def test_source_node_default_metadata(self) -> None:
        from backend.src.models.domain import SourceNode

        node = SourceNode(text="text", score=0.5)
        assert node.metadata == {}


class TestCreateQueryIndex:
    @patch("backend.src.tools.rag_tool.VectorStoreIndex.from_vector_store")
    @patch("backend.src.tools.rag_tool.create_vector_store")
    def test_creates_index_from_vector_store(self, mock_create_vs: MagicMock, mock_from_vs: MagicMock) -> None:
        from backend.src.tools.rag_tool import create_query_index

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        mock_vs = MagicMock()
        mock_create_vs.return_value = mock_vs
        mock_index = MagicMock()
        mock_from_vs.return_value = mock_index

        result = create_query_index(settings)

        mock_create_vs.assert_called_once_with(settings)
        mock_from_vs.assert_called_once_with(vector_store=mock_vs)
        assert result is mock_index


class TestCreateQueryEngine:
    @patch("backend.src.tools.rag_tool.create_query_index")
    def test_creates_query_engine_with_rag_settings(self, mock_create_index: MagicMock) -> None:
        from backend.src.tools.rag_tool import create_query_engine

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        mock_index = MagicMock()
        mock_create_index.return_value = mock_index
        mock_engine = MagicMock()
        mock_index.as_query_engine.return_value = mock_engine

        result = create_query_engine(settings)

        mock_index.as_query_engine.assert_called_once_with(
            similarity_top_k=settings.rag.similarity_top_k,
            response_mode=settings.rag.response_mode,
        )
        assert result is mock_engine

    @patch("backend.src.tools.rag_tool.create_query_index")
    def test_uses_custom_rag_settings(self, mock_create_index: MagicMock) -> None:
        from backend.src.tools.rag_tool import create_query_engine

        settings = Settings(
            _env_file=None,
            openai_api_key="sk-test",  # pragma: allowlist secret
            rag=RAGSettings(similarity_top_k=10, response_mode="compact"),
        )
        mock_index = MagicMock()
        mock_create_index.return_value = mock_index
        mock_index.as_query_engine.return_value = MagicMock()

        create_query_engine(settings)

        mock_index.as_query_engine.assert_called_once_with(
            similarity_top_k=10,
            response_mode="compact",
        )


class TestExecuteQuery:
    @patch("backend.src.tools.rag_tool.create_query_engine")
    def test_returns_query_result(self, mock_create_engine: MagicMock) -> None:
        from backend.src.models.domain import QueryResult
        from backend.src.tools.rag_tool import execute_query

        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        mock_source = MagicMock()
        mock_source.node.get_content.return_value = "source text"
        mock_source.score = 0.92
        mock_source.node.metadata = {"file": "report.pdf"}

        mock_response = MagicMock()
        mock_response.__str__ = MagicMock(return_value="The Q4 revenue was $127.3M.")
        mock_response.source_nodes = [mock_source]

        mock_engine.query.return_value = mock_response

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        result = execute_query("What was Q4 revenue?", settings)

        assert isinstance(result, QueryResult)
        assert result.answer == "The Q4 revenue was $127.3M."
        assert len(result.source_nodes) == 1
        assert result.source_nodes[0].text == "source text"
        assert result.source_nodes[0].score == 0.92

    @patch("backend.src.tools.rag_tool.create_query_engine")
    def test_calls_query_engine_with_text(self, mock_create_engine: MagicMock) -> None:
        from backend.src.tools.rag_tool import execute_query

        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        mock_response = MagicMock()
        mock_response.__str__ = MagicMock(return_value="answer")
        mock_response.source_nodes = []
        mock_engine.query.return_value = mock_response

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        execute_query("my question", settings)

        mock_engine.query.assert_called_once_with("my question")

    @patch("backend.src.tools.rag_tool.create_query_engine")
    def test_returns_failed_result_on_error(self, mock_create_engine: MagicMock) -> None:
        from backend.src.models.domain import QueryResult
        from backend.src.tools.rag_tool import execute_query

        mock_create_engine.side_effect = RuntimeError("connection failed")

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        result = execute_query("test query", settings)

        assert isinstance(result, QueryResult)
        assert "connection failed" in result.answer
        assert result.source_nodes == []

    @patch("backend.src.tools.rag_tool.create_query_engine")
    def test_handles_empty_response(self, mock_create_engine: MagicMock) -> None:
        from backend.src.tools.rag_tool import execute_query

        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        mock_response = MagicMock()
        mock_response.__str__ = MagicMock(return_value="")
        mock_response.__bool__ = MagicMock(return_value=False)
        mock_response.source_nodes = []
        mock_engine.query.return_value = mock_response

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        result = execute_query("test", settings)

        assert result.answer == ""
        assert result.source_nodes == []

    @patch("backend.src.tools.rag_tool.create_query_engine")
    def test_extracts_multiple_source_nodes(self, mock_create_engine: MagicMock) -> None:
        from backend.src.tools.rag_tool import execute_query

        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        sources = []
        for i in range(3):
            s = MagicMock()
            s.node.get_content.return_value = f"text {i}"
            s.score = 0.9 - i * 0.1
            s.node.metadata = {}
            sources.append(s)

        mock_response = MagicMock()
        mock_response.__str__ = MagicMock(return_value="combined answer")
        mock_response.source_nodes = sources
        mock_engine.query.return_value = mock_response

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        result = execute_query("query", settings)

        assert result.answer == "combined answer"
        assert len(result.source_nodes) == 3
        assert result.source_nodes[0].score == pytest.approx(0.9)
        assert result.source_nodes[2].score == pytest.approx(0.7)
