"""Tests for document ingestion pipeline components."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.src.core.config import RAGSettings, Settings
from backend.src.models.domain import IngestionResult


class TestIngestionResult:
    def test_ingestion_result_has_required_fields(self):
        result = IngestionResult(
            document_count=3,
            node_count=15,
            status="success",
        )
        assert result.document_count == 3
        assert result.node_count == 15
        assert result.status == "success"

    def test_ingestion_result_failed_status(self):
        result = IngestionResult(
            document_count=0,
            node_count=0,
            status="failed",
            error_message="Connection refused",
        )
        assert result.status == "failed"
        assert result.error_message == "Connection refused"

    def test_ingestion_result_error_message_defaults_to_none(self):
        result = IngestionResult(
            document_count=1,
            node_count=5,
            status="success",
        )
        assert result.error_message is None


class TestSupportedExtensions:
    def test_supported_extensions_includes_pdf(self):
        from backend.src.ingestion.parsers import SUPPORTED_EXTENSIONS

        assert ".pdf" in SUPPORTED_EXTENSIONS

    def test_supported_extensions_includes_docx(self):
        from backend.src.ingestion.parsers import SUPPORTED_EXTENSIONS

        assert ".docx" in SUPPORTED_EXTENSIONS

    def test_supported_extensions_includes_txt(self):
        from backend.src.ingestion.parsers import SUPPORTED_EXTENSIONS

        assert ".txt" in SUPPORTED_EXTENSIONS

    def test_supported_extensions_includes_xlsx(self):
        from backend.src.ingestion.parsers import SUPPORTED_EXTENSIONS

        assert ".xlsx" in SUPPORTED_EXTENSIONS

    def test_supported_extensions_includes_csv(self):
        from backend.src.ingestion.parsers import SUPPORTED_EXTENSIONS

        assert ".csv" in SUPPORTED_EXTENSIONS

    def test_supported_extensions_includes_md(self):
        from backend.src.ingestion.parsers import SUPPORTED_EXTENSIONS

        assert ".md" in SUPPORTED_EXTENSIONS


class TestLoadDocuments:
    @patch("backend.src.ingestion.parsers.SimpleDirectoryReader")
    def test_load_documents_calls_simple_directory_reader(self, mock_reader_cls, tmp_path):
        from backend.src.ingestion.parsers import load_documents

        mock_reader = MagicMock()
        mock_reader.load_data.return_value = []
        mock_reader_cls.return_value = mock_reader

        load_documents(tmp_path)

        mock_reader_cls.assert_called_once()
        mock_reader.load_data.assert_called_once()

    @patch("backend.src.ingestion.parsers.SimpleDirectoryReader")
    def test_load_documents_passes_directory_path(self, mock_reader_cls, tmp_path):
        from backend.src.ingestion.parsers import load_documents

        mock_reader = MagicMock()
        mock_reader.load_data.return_value = []
        mock_reader_cls.return_value = mock_reader

        load_documents(tmp_path)

        call_kwargs = mock_reader_cls.call_args
        assert call_kwargs[1]["input_dir"] == tmp_path

    @patch("backend.src.ingestion.parsers.SimpleDirectoryReader")
    def test_load_documents_filters_by_supported_extensions(self, mock_reader_cls, tmp_path):
        from backend.src.ingestion.parsers import SUPPORTED_EXTENSIONS, load_documents

        mock_reader = MagicMock()
        mock_reader.load_data.return_value = []
        mock_reader_cls.return_value = mock_reader

        load_documents(tmp_path)

        call_kwargs = mock_reader_cls.call_args
        assert set(call_kwargs[1]["required_exts"]) == set(SUPPORTED_EXTENSIONS)

    @patch("backend.src.ingestion.parsers.SimpleDirectoryReader")
    def test_load_documents_returns_document_list(self, mock_reader_cls, tmp_path):
        from backend.src.ingestion.parsers import load_documents

        mock_doc = MagicMock()
        mock_reader = MagicMock()
        mock_reader.load_data.return_value = [mock_doc]
        mock_reader_cls.return_value = mock_reader

        result = load_documents(tmp_path)

        assert result == [mock_doc]

    def test_load_documents_raises_for_nonexistent_directory(self):
        from backend.src.ingestion.parsers import load_documents

        with pytest.raises(FileNotFoundError):
            load_documents(Path("/nonexistent/directory/that/does/not/exist"))

    @patch("backend.src.ingestion.parsers.SimpleDirectoryReader")
    def test_load_documents_enables_recursive_reading(self, mock_reader_cls, tmp_path):
        from backend.src.ingestion.parsers import load_documents

        mock_reader = MagicMock()
        mock_reader.load_data.return_value = []
        mock_reader_cls.return_value = mock_reader

        load_documents(tmp_path)

        call_kwargs = mock_reader_cls.call_args
        assert call_kwargs[1]["recursive"] is True


class TestCreateSentenceSplitter:
    def test_splitter_uses_rag_settings_chunk_size(self):
        from backend.src.ingestion.chunking import create_sentence_splitter

        rag = RAGSettings(chunk_size=256, chunk_overlap=25)
        splitter = create_sentence_splitter(rag)
        assert splitter.chunk_size == 256

    def test_splitter_uses_rag_settings_chunk_overlap(self):
        from backend.src.ingestion.chunking import create_sentence_splitter

        rag = RAGSettings(chunk_size=512, chunk_overlap=100)
        splitter = create_sentence_splitter(rag)
        assert splitter.chunk_overlap == 100

    def test_splitter_uses_defaults_from_rag_settings(self):
        from backend.src.ingestion.chunking import create_sentence_splitter

        rag = RAGSettings()
        splitter = create_sentence_splitter(rag)
        assert splitter.chunk_size == 512
        assert splitter.chunk_overlap == 50


class TestCreateVectorStore:
    @patch("backend.src.ingestion.pipeline.PGVectorStore.from_params")
    def test_creates_pgvector_store_with_correct_params(self, mock_from_params):
        from backend.src.ingestion.pipeline import create_vector_store

        settings = Settings()
        mock_from_params.return_value = MagicMock()

        create_vector_store(settings)

        mock_from_params.assert_called_once()
        call_kwargs = mock_from_params.call_args[1]
        assert call_kwargs["database"] == settings.postgres.database
        assert call_kwargs["host"] == settings.postgres.host
        assert call_kwargs["port"] == str(settings.postgres.port)
        assert call_kwargs["user"] == settings.postgres.user
        assert call_kwargs["table_name"] == settings.postgres.vector_table
        assert call_kwargs["embed_dim"] == settings.embedding_dimension

    @patch("backend.src.ingestion.pipeline.PGVectorStore.from_params")
    def test_creates_pgvector_store_with_password(self, mock_from_params):
        from backend.src.ingestion.pipeline import create_vector_store

        settings = Settings()
        mock_from_params.return_value = MagicMock()

        create_vector_store(settings)

        call_kwargs = mock_from_params.call_args[1]
        assert call_kwargs["password"] == settings.postgres.password.get_secret_value()

    @patch("backend.src.ingestion.pipeline.PGVectorStore.from_params")
    def test_creates_pgvector_store_with_hnsw_kwargs(self, mock_from_params):
        from backend.src.ingestion.pipeline import create_vector_store

        settings = Settings()
        mock_from_params.return_value = MagicMock()

        create_vector_store(settings)

        call_kwargs = mock_from_params.call_args[1]
        assert "hnsw_kwargs" in call_kwargs
        hnsw = call_kwargs["hnsw_kwargs"]
        assert hnsw["hnsw_m"] == 16
        assert "hnsw_ef_construction" in hnsw
        assert hnsw["hnsw_dist_method"] == "vector_cosine_ops"


class TestCreateIngestionPipeline:
    @patch("backend.src.ingestion.pipeline.create_vector_store")
    @patch("backend.src.ingestion.pipeline.IngestionPipeline")
    def test_pipeline_includes_sentence_splitter(self, mock_pipeline_cls, mock_vs):
        from backend.src.ingestion.pipeline import create_ingestion_pipeline

        mock_vs.return_value = MagicMock()
        mock_pipeline_cls.return_value = MagicMock()

        create_ingestion_pipeline(Settings())

        call_kwargs = mock_pipeline_cls.call_args[1]
        transformations = call_kwargs["transformations"]
        type_names = [type(t).__name__ for t in transformations]
        assert "SentenceSplitter" in type_names

    @patch("backend.src.ingestion.pipeline.create_vector_store")
    @patch("backend.src.ingestion.pipeline.IngestionPipeline")
    def test_pipeline_includes_embedding_model(self, mock_pipeline_cls, mock_vs):
        from backend.src.ingestion.pipeline import create_ingestion_pipeline

        mock_vs.return_value = MagicMock()
        mock_pipeline_cls.return_value = MagicMock()

        create_ingestion_pipeline(Settings())

        call_kwargs = mock_pipeline_cls.call_args[1]
        transformations = call_kwargs["transformations"]
        type_names = [type(t).__name__ for t in transformations]
        assert "OpenAIEmbedding" in type_names

    @patch("backend.src.ingestion.pipeline.create_vector_store")
    @patch("backend.src.ingestion.pipeline.IngestionPipeline")
    def test_pipeline_connects_to_vector_store(self, mock_pipeline_cls, mock_vs):
        from backend.src.ingestion.pipeline import create_ingestion_pipeline

        mock_store = MagicMock()
        mock_vs.return_value = mock_store
        mock_pipeline_cls.return_value = MagicMock()

        create_ingestion_pipeline(Settings())

        call_kwargs = mock_pipeline_cls.call_args[1]
        assert call_kwargs["vector_store"] is mock_store


class TestIngestDocuments:
    @patch("backend.src.ingestion.pipeline.create_ingestion_pipeline")
    @patch("backend.src.ingestion.pipeline.load_documents")
    def test_ingest_returns_ingestion_result(self, mock_load, mock_create_pipeline):
        from backend.src.ingestion.pipeline import ingest_documents

        mock_doc = MagicMock()
        mock_load.return_value = [mock_doc]
        mock_pipeline = MagicMock()
        mock_node = MagicMock()
        mock_pipeline.run.return_value = [mock_node, mock_node, mock_node]
        mock_create_pipeline.return_value = mock_pipeline

        result = ingest_documents(Path("/fake/dir"), Settings())

        assert isinstance(result, IngestionResult)
        assert result.document_count == 1
        assert result.node_count == 3
        assert result.status == "success"

    @patch("backend.src.ingestion.pipeline.create_ingestion_pipeline")
    @patch("backend.src.ingestion.pipeline.load_documents")
    def test_ingest_returns_failed_on_error(self, mock_load, mock_create_pipeline):
        from backend.src.ingestion.pipeline import ingest_documents

        mock_load.side_effect = FileNotFoundError("No such directory")

        result = ingest_documents(Path("/fake/dir"), Settings())

        assert result.status == "failed"
        assert result.document_count == 0
        assert result.node_count == 0
        assert "No such directory" in result.error_message

    @patch("backend.src.ingestion.pipeline.create_ingestion_pipeline")
    @patch("backend.src.ingestion.pipeline.load_documents")
    def test_ingest_calls_pipeline_run_with_documents(self, mock_load, mock_create_pipeline):
        from backend.src.ingestion.pipeline import ingest_documents

        mock_docs = [MagicMock(), MagicMock()]
        mock_load.return_value = mock_docs
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = []
        mock_create_pipeline.return_value = mock_pipeline

        ingest_documents(Path("/fake/dir"), Settings())

        mock_pipeline.run.assert_called_once_with(documents=mock_docs)
