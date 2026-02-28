"""Tests for the startup seed module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.src.core.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        openai_api_key="sk-test",  # type: ignore[arg-type]
        debug=True,
    )


class TestEnsureDefaultCollection:
    @patch("backend.src.api.seed.select")
    def test_returns_existing_collection(self, mock_select: MagicMock) -> None:
        from backend.src.api.seed import _ensure_default_collection

        existing = MagicMock()
        existing.id = "existing-id"
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = existing

        result = _ensure_default_collection(mock_session)

        assert result is existing
        mock_session.add.assert_not_called()

    @patch("backend.src.api.seed.select")
    def test_creates_collection_when_missing(self, mock_select: MagicMock) -> None:
        from backend.src.api.seed import _ensure_default_collection

        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        result = _ensure_default_collection(mock_session)

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        assert result.name == "leadership"


class TestBusinessMetricsHasData:
    def test_returns_true_when_rows_exist(self) -> None:
        from backend.src.api.seed import _business_metrics_has_data

        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = 1

        assert _business_metrics_has_data(mock_session) is True

    def test_returns_false_when_empty(self) -> None:
        from backend.src.api.seed import _business_metrics_has_data

        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        assert _business_metrics_has_data(mock_session) is False


class TestSeedSampleDocuments:
    @patch("backend.src.api.seed.ingest_documents")
    @patch("backend.src.api.seed._vector_store_has_data", return_value=False)
    def test_seeds_when_store_empty(
        self,
        mock_has_data: MagicMock,
        mock_ingest: MagicMock,
        settings: Settings,
    ) -> None:
        from backend.src.api.seed import seed_sample_documents

        mock_ingest.return_value = MagicMock(status="success", document_count=3, node_count=15)
        seed_sample_documents(settings)

        mock_has_data.assert_called_once_with(settings)
        mock_ingest.assert_called_once()

    @patch("backend.src.api.seed.ingest_documents")
    @patch("backend.src.api.seed._vector_store_has_data", return_value=True)
    def test_skips_when_store_has_data(
        self,
        mock_has_data: MagicMock,
        mock_ingest: MagicMock,
        settings: Settings,
    ) -> None:
        from backend.src.api.seed import seed_sample_documents

        seed_sample_documents(settings)

        mock_has_data.assert_called_once_with(settings)
        mock_ingest.assert_not_called()

    @patch("backend.src.api.seed.ingest_documents")
    @patch("backend.src.api.seed._vector_store_has_data", return_value=False)
    @patch("backend.src.api.seed._SAMPLE_DOCS_DIR", new=Path("/nonexistent/path"))
    def test_skips_when_sample_dir_missing(
        self,
        mock_has_data: MagicMock,
        mock_ingest: MagicMock,
        settings: Settings,
    ) -> None:
        from backend.src.api.seed import seed_sample_documents

        seed_sample_documents(settings)

        mock_ingest.assert_not_called()

    @patch("backend.src.api.seed.ingest_documents")
    @patch("backend.src.api.seed._vector_store_has_data", side_effect=Exception("DB error"))
    def test_handles_check_failure_gracefully(
        self,
        mock_has_data: MagicMock,
        mock_ingest: MagicMock,
        settings: Settings,
    ) -> None:
        from backend.src.api.seed import seed_sample_documents

        seed_sample_documents(settings)
        mock_ingest.assert_not_called()

    @patch("backend.src.api.seed.ingest_documents", side_effect=Exception("Ingestion failed"))
    @patch("backend.src.api.seed._vector_store_has_data", return_value=False)
    def test_handles_ingestion_failure_gracefully(
        self,
        mock_has_data: MagicMock,
        mock_ingest: MagicMock,
        settings: Settings,
    ) -> None:
        from backend.src.api.seed import seed_sample_documents

        seed_sample_documents(settings)
        mock_ingest.assert_called_once()


class TestSeedBusinessMetrics:
    @patch("backend.src.api.seed.ingest_excel_to_business_metrics", return_value=72)
    @patch("backend.src.api.seed._business_metrics_has_data", return_value=False)
    @patch("backend.src.api.seed._find_excel_files")
    def test_seeds_metrics_from_excel(
        self,
        mock_find: MagicMock,
        mock_has_data: MagicMock,
        mock_ingest: MagicMock,
    ) -> None:
        from backend.src.api.seed import seed_business_metrics

        mock_session = MagicMock()
        mock_find.return_value = [Path("kpis.xlsx")]

        seed_business_metrics(mock_session, "coll-id")

        mock_has_data.assert_called_once_with(mock_session)
        mock_ingest.assert_called_once_with(Path("kpis.xlsx"), mock_session, "coll-id")

    @patch("backend.src.api.seed.ingest_excel_to_business_metrics")
    @patch("backend.src.api.seed._business_metrics_has_data", return_value=True)
    def test_skips_when_metrics_exist(
        self,
        mock_has_data: MagicMock,
        mock_ingest: MagicMock,
    ) -> None:
        from backend.src.api.seed import seed_business_metrics

        mock_session = MagicMock()

        seed_business_metrics(mock_session, "coll-id")

        mock_has_data.assert_called_once_with(mock_session)
        mock_ingest.assert_not_called()

    @patch("backend.src.api.seed.ingest_excel_to_business_metrics", side_effect=Exception("parse fail"))
    @patch("backend.src.api.seed._business_metrics_has_data", return_value=False)
    @patch("backend.src.api.seed._find_excel_files")
    def test_handles_failure_gracefully(
        self,
        mock_find: MagicMock,
        mock_has_data: MagicMock,
        mock_ingest: MagicMock,
    ) -> None:
        from backend.src.api.seed import seed_business_metrics

        mock_session = MagicMock()
        mock_find.return_value = [Path("kpis.xlsx")]

        seed_business_metrics(mock_session, "coll-id")

        mock_ingest.assert_called_once()

    @patch("backend.src.api.seed.ingest_excel_to_business_metrics")
    @patch("backend.src.api.seed._business_metrics_has_data", return_value=False)
    @patch("backend.src.api.seed._find_excel_files", return_value=[])
    def test_skips_when_no_excel_files(
        self,
        mock_find: MagicMock,
        mock_has_data: MagicMock,
        mock_ingest: MagicMock,
    ) -> None:
        from backend.src.api.seed import seed_business_metrics

        mock_session = MagicMock()

        seed_business_metrics(mock_session, "coll-id")

        mock_ingest.assert_not_called()


class TestVectorStoreHasData:
    @patch("backend.src.api.seed.create_vector_store")
    def test_returns_false_when_table_missing(self, mock_create: MagicMock, settings: Settings) -> None:
        from backend.src.api.seed import _vector_store_has_data

        mock_store = MagicMock()
        mock_store._engine = MagicMock()  # noqa: SLF001
        mock_create.return_value = mock_store

        with patch("backend.src.api.seed.inspect") as mock_inspect:
            mock_inspector = MagicMock()
            mock_inspector.get_table_names.return_value = []
            mock_inspect.return_value = mock_inspector
            result = _vector_store_has_data(settings)

        assert result is False

    @patch("backend.src.api.seed.create_vector_store")
    def test_returns_true_when_rows_exist(self, mock_create: MagicMock, settings: Settings) -> None:
        from backend.src.api.seed import _vector_store_has_data

        mock_store = MagicMock()
        mock_store._engine = MagicMock()  # noqa: SLF001
        mock_store.table_name = "document_vectors"
        mock_create.return_value = mock_store

        with patch("backend.src.api.seed.inspect") as mock_inspect:
            mock_inspector = MagicMock()
            mock_inspector.get_table_names.return_value = ["document_vectors"]
            mock_inspect.return_value = mock_inspector

            with patch("backend.src.api.seed._table_has_rows", return_value=True):
                result = _vector_store_has_data(settings)

        assert result is True
