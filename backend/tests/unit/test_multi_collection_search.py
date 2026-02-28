"""Tests for multi-collection vector search functionality."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.src.core.config import Settings


class TestCreateVectorStoreWithCollection:
    @patch("backend.src.ingestion.pipeline.PGVectorStore.from_params")
    def test_uses_default_table_without_override(self, mock_from_params: MagicMock) -> None:
        from backend.src.ingestion.pipeline import create_vector_store

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        create_vector_store(settings)

        mock_from_params.assert_called_once()
        call_kwargs = mock_from_params.call_args[1]
        assert call_kwargs["table_name"] == settings.postgres.vector_table

    @patch("backend.src.ingestion.pipeline.PGVectorStore.from_params")
    def test_uses_custom_table_name_when_provided(self, mock_from_params: MagicMock) -> None:
        from backend.src.ingestion.pipeline import create_vector_store

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        create_vector_store(settings, table_name="vec_my_collection_abc123")

        mock_from_params.assert_called_once()
        call_kwargs = mock_from_params.call_args[1]
        assert call_kwargs["table_name"] == "vec_my_collection_abc123"

    @patch("backend.src.ingestion.pipeline.PGVectorStore.from_params")
    def test_preserves_hnsw_defaults(self, mock_from_params: MagicMock) -> None:
        from backend.src.ingestion.pipeline import create_vector_store

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        create_vector_store(settings, table_name="vec_custom")

        call_kwargs = mock_from_params.call_args[1]
        assert call_kwargs["hnsw_kwargs"]["hnsw_m"] == 16
        assert call_kwargs["hnsw_kwargs"]["hnsw_ef_construction"] == 64
        assert call_kwargs["embed_dim"] == settings.embedding_dimension


class TestIngestDocumentsWithCollection:
    @patch("backend.src.ingestion.pipeline.create_ingestion_pipeline")
    @patch("backend.src.ingestion.pipeline.load_documents")
    def test_ingest_passes_table_name_to_pipeline(
        self,
        mock_load: MagicMock,
        mock_create_pipeline: MagicMock,
        tmp_path: MagicMock,
    ) -> None:
        from backend.src.ingestion.pipeline import ingest_documents

        mock_load.return_value = [MagicMock()]
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = [MagicMock()]
        mock_create_pipeline.return_value = mock_pipeline

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        result = ingest_documents(tmp_path, settings, table_name="vec_custom_table")

        mock_create_pipeline.assert_called_once_with(settings, table_name="vec_custom_table")
        assert result.status == "success"

    @patch("backend.src.ingestion.pipeline.create_ingestion_pipeline")
    @patch("backend.src.ingestion.pipeline.load_documents")
    def test_ingest_uses_default_table_without_override(
        self,
        mock_load: MagicMock,
        mock_create_pipeline: MagicMock,
        tmp_path: MagicMock,
    ) -> None:
        from backend.src.ingestion.pipeline import ingest_documents

        mock_load.return_value = [MagicMock()]
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = [MagicMock()]
        mock_create_pipeline.return_value = mock_pipeline

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        ingest_documents(tmp_path, settings)

        mock_create_pipeline.assert_called_once_with(settings, table_name=None)


class TestCreateQueryEngineWithCollection:
    @patch("backend.src.tools.rag_tool.create_query_index")
    def test_passes_table_name_to_index(self, mock_create_index: MagicMock) -> None:
        from backend.src.tools.rag_tool import create_query_engine

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        mock_index = MagicMock()
        mock_create_index.return_value = mock_index
        mock_index.as_query_engine.return_value = MagicMock()

        create_query_engine(settings, table_name="vec_collection_x")

        mock_create_index.assert_called_once_with(settings, table_name="vec_collection_x")

    @patch("backend.src.tools.rag_tool.create_query_index")
    def test_uses_default_without_table_name(self, mock_create_index: MagicMock) -> None:
        from backend.src.tools.rag_tool import create_query_engine

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        mock_index = MagicMock()
        mock_create_index.return_value = mock_index
        mock_index.as_query_engine.return_value = MagicMock()

        create_query_engine(settings)

        mock_create_index.assert_called_once_with(settings, table_name=None)


class TestCreateQueryIndexWithCollection:
    @patch("backend.src.tools.rag_tool.VectorStoreIndex.from_vector_store")
    @patch("backend.src.tools.rag_tool.create_vector_store")
    def test_passes_table_name_to_vector_store(
        self,
        mock_create_vs: MagicMock,
        mock_from_vs: MagicMock,
    ) -> None:
        from backend.src.tools.rag_tool import create_query_index

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        mock_create_vs.return_value = MagicMock()
        mock_from_vs.return_value = MagicMock()

        create_query_index(settings, table_name="vec_custom")

        mock_create_vs.assert_called_once_with(settings, table_name="vec_custom")


class TestExecuteQueryWithCollection:
    @patch("backend.src.tools.rag_tool.create_query_engine")
    def test_passes_table_name_to_engine(self, mock_create_engine: MagicMock) -> None:
        from backend.src.tools.rag_tool import execute_query

        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        mock_response = MagicMock()
        mock_response.__str__ = MagicMock(return_value="answer")
        mock_response.source_nodes = []
        mock_engine.query.return_value = mock_response

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        execute_query("question", settings, table_name="vec_my_table")

        mock_create_engine.assert_called_once_with(settings, table_name="vec_my_table")

    @patch("backend.src.tools.rag_tool.create_query_engine")
    def test_uses_default_without_table_name(self, mock_create_engine: MagicMock) -> None:
        from backend.src.tools.rag_tool import execute_query

        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        mock_response = MagicMock()
        mock_response.__str__ = MagicMock(return_value="answer")
        mock_response.source_nodes = []
        mock_engine.query.return_value = mock_response

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        execute_query("question", settings)

        mock_create_engine.assert_called_once_with(settings, table_name=None)


class TestQueryRequestCollectionId:
    def test_query_request_with_collection_id(self) -> None:
        from backend.src.models.schemas import QueryRequest

        req = QueryRequest(query="What is revenue?", collection_id="abc-123")
        assert req.collection_id == "abc-123"

    def test_query_request_defaults_to_no_collection(self) -> None:
        from backend.src.models.schemas import QueryRequest

        req = QueryRequest(query="What is revenue?")
        assert req.collection_id is None


class TestCollectionIngestUsesVectorTable:
    @patch("backend.src.api.collection_routes.ingest_documents")
    def test_run_collection_ingestion_passes_vector_table(
        self,
        mock_ingest: MagicMock,
        tmp_path: MagicMock,
    ) -> None:
        from backend.src.api.collection_routes import _run_collection_ingestion

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        mock_ingest.return_value = MagicMock(status="success", document_count=1, node_count=5)

        _run_collection_ingestion(tmp_path, settings, vector_table="vec_my_collection")

        mock_ingest.assert_called_once_with(tmp_path, settings, table_name="vec_my_collection")
