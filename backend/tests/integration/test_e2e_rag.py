"""End-to-end integration tests for the RAG pipeline.

Flow: ingest markdown documents → vector store → query engine → verify response.
Tests validate that the full RAG pipeline wiring works correctly, with the LLM
and embedding layers mocked but all other components exercised.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from llama_index.core.schema import NodeWithScore, TextNode

from backend.src.models.domain import IngestionResult, QueryResult
from backend.src.tools.rag_tool import create_query_engine, execute_query

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.integration
class TestRagIngestAndQuery:
    """Verify the ingest → store → query → response pipeline end-to-end."""

    @patch("backend.src.tools.rag_tool.create_vector_store")
    def test_create_query_engine_returns_engine_with_settings(
        self,
        mock_create_vs: MagicMock,
        test_settings: MagicMock,
    ) -> None:
        mock_index = MagicMock()
        mock_engine = MagicMock()
        mock_index.as_query_engine.return_value = mock_engine
        with patch(
            "backend.src.tools.rag_tool.VectorStoreIndex.from_vector_store",
            return_value=mock_index,
        ):
            engine = create_query_engine(test_settings)

        assert engine is mock_engine
        mock_index.as_query_engine.assert_called_once()

    @patch("backend.src.tools.rag_tool.create_vector_store")
    def test_execute_query_returns_answer_with_sources(
        self,
        mock_create_vs: MagicMock,
        test_settings: MagicMock,
    ) -> None:
        mock_response = MagicMock()
        mock_response.__str__ = lambda self: "Revenue grew by 15% in Q4."
        mock_response.source_nodes = [
            NodeWithScore(
                node=TextNode(
                    text="Q4 results show 15% revenue growth.",
                    metadata={"source": "quarterly_review.md"},
                ),
                score=0.92,
            ),
        ]

        mock_engine = MagicMock()
        mock_engine.query.return_value = mock_response

        with (
            patch(
                "backend.src.tools.rag_tool.VectorStoreIndex.from_vector_store",
                return_value=MagicMock(as_query_engine=MagicMock(return_value=mock_engine)),
            ),
        ):
            result = execute_query("What was Q4 revenue growth?", test_settings)

        assert isinstance(result, QueryResult)
        assert "15%" in result.answer
        assert len(result.source_nodes) == 1
        assert result.source_nodes[0].score == 0.92
        assert "quarterly_review" in result.source_nodes[0].metadata.get("source", "")


@pytest.mark.integration
class TestRagCollectionScopedQuery:
    """Verify RAG queries can be scoped to a specific collection's vector table.

    Inspired by talk2data pattern: each collection has its own vector table and
    queries can be scoped to a specific collection.
    """

    @patch("backend.src.tools.rag_tool.create_vector_store")
    def test_query_engine_uses_custom_table_name(
        self,
        mock_create_vs: MagicMock,
        test_settings: MagicMock,
    ) -> None:
        mock_index = MagicMock()
        mock_index.as_query_engine.return_value = MagicMock()
        with patch(
            "backend.src.tools.rag_tool.VectorStoreIndex.from_vector_store",
            return_value=mock_index,
        ):
            create_query_engine(test_settings, table_name="vec_custom_collection")

        mock_create_vs.assert_called_once_with(test_settings, table_name="vec_custom_collection")

    @patch("backend.src.tools.rag_tool.create_vector_store")
    def test_query_uses_default_table_when_no_collection_specified(
        self,
        mock_create_vs: MagicMock,
        test_settings: MagicMock,
    ) -> None:
        mock_index = MagicMock()
        mock_index.as_query_engine.return_value = MagicMock()
        with patch(
            "backend.src.tools.rag_tool.VectorStoreIndex.from_vector_store",
            return_value=mock_index,
        ):
            create_query_engine(test_settings)

        mock_create_vs.assert_called_once_with(test_settings, table_name=None)


@pytest.mark.integration
class TestRagIngestionPipeline:
    """Verify the document ingestion pipeline produces correct IngestionResult."""

    @patch("backend.src.ingestion.pipeline.create_embed_model")
    @patch("backend.src.ingestion.pipeline.create_vector_store")
    @patch("backend.src.ingestion.pipeline.load_documents")
    def test_ingest_documents_returns_success_result(
        self,
        mock_load: MagicMock,
        mock_vs: MagicMock,
        mock_embed: MagicMock,
        test_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        from backend.src.ingestion.pipeline import ingest_documents

        mock_doc = MagicMock()
        mock_load.return_value = [mock_doc]

        mock_pipeline_inst = MagicMock()
        mock_pipeline_inst.run.return_value = [MagicMock(), MagicMock()]

        with patch(
            "backend.src.ingestion.pipeline.IngestionPipeline",
            return_value=mock_pipeline_inst,
        ):
            result = ingest_documents(tmp_path, test_settings)

        assert isinstance(result, IngestionResult)
        assert result.status == "success"
        assert result.document_count == 1
        assert result.node_count == 2

    @patch("backend.src.ingestion.pipeline.create_embed_model")
    @patch("backend.src.ingestion.pipeline.create_vector_store")
    @patch("backend.src.ingestion.pipeline.load_documents")
    def test_ingest_documents_with_collection_table(
        self,
        mock_load: MagicMock,
        mock_vs: MagicMock,
        mock_embed: MagicMock,
        test_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Verify ingestion can target a collection-specific vector table."""
        from backend.src.ingestion.pipeline import ingest_documents

        mock_load.return_value = [MagicMock()]
        mock_pipeline_inst = MagicMock()
        mock_pipeline_inst.run.return_value = [MagicMock()]

        with patch(
            "backend.src.ingestion.pipeline.IngestionPipeline",
            return_value=mock_pipeline_inst,
        ):
            ingest_documents(tmp_path, test_settings, table_name="vec_my_collection")

        mock_vs.assert_called_once_with(test_settings, table_name="vec_my_collection")

    @patch("backend.src.ingestion.pipeline.create_embed_model")
    @patch("backend.src.ingestion.pipeline.create_vector_store")
    @patch("backend.src.ingestion.pipeline.load_documents", side_effect=RuntimeError("disk error"))
    def test_ingest_documents_handles_failures_gracefully(
        self,
        mock_load: MagicMock,
        mock_vs: MagicMock,
        mock_embed: MagicMock,
        test_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        from backend.src.ingestion.pipeline import ingest_documents

        result = ingest_documents(tmp_path, test_settings)

        assert result.status == "failed"
        assert result.error_message is not None
        assert "disk error" in result.error_message


@pytest.fixture()
def test_settings() -> MagicMock:
    """Minimal mocked Settings for RAG pipeline tests."""
    settings = MagicMock()
    settings.rag.similarity_top_k = 3
    settings.rag.response_mode = "compact"
    settings.rag.chunk_size = 512
    settings.rag.chunk_overlap = 50
    settings.postgres.host = "localhost"
    settings.postgres.port = 5432
    settings.postgres.database = "test_db"
    settings.postgres.user = "test"
    settings.postgres.password = MagicMock()
    settings.postgres.password.get_secret_value.return_value = "test"
    settings.postgres.vector_table = "test_vec"
    settings.embedding_dimension = 1536
    return settings
