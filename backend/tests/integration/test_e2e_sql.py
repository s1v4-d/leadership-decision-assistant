"""End-to-end integration tests for the NL2SQL pipeline.

Flow: create structured tables → insert BusinessMetric rows → NLSQLTableQueryEngine
→ query → verify answer.

Tests validate that structured data flows correctly from ingestion through the
SQL query engine. The LLM layer is mocked but the actual SQL execution path
(SQLAlchemy engine → SQLDatabase → query) is exercised against an in-memory
SQLite database.

Inspired by talk2data pattern: structured data lives in its own schema
(sql_schema) alongside vector data (vector_schema) in the same PostgreSQL
instance, and queries can be filtered by collection.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.src.models.tables import Base, BusinessMetric, Collection


@pytest.fixture()
def sqlite_engine():
    """Create an in-memory SQLite engine with all ORM tables."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def sqlite_session(sqlite_engine) -> Session:
    """Provide a SQLAlchemy session backed by in-memory SQLite."""
    factory = sessionmaker(bind=sqlite_engine)
    session = factory()
    yield session
    session.close()


@pytest.fixture()
def seeded_collection(sqlite_session: Session) -> Collection:
    """Insert a default collection and return it."""
    collection = Collection(
        id="test-col-001",
        name="leadership",
        description="Test leadership collection",
        vector_table="vec_leadership_test",
    )
    sqlite_session.add(collection)
    sqlite_session.commit()
    return collection


@pytest.fixture()
def seeded_metrics(sqlite_session: Session, seeded_collection: Collection) -> list[BusinessMetric]:
    """Insert sample business metrics for testing."""
    metrics = [
        BusinessMetric(
            id="m-001",
            collection_id=seeded_collection.id,
            metric_name="Revenue",
            metric_value=1250000.0,
            unit="USD",
            period="2025-Q4",
            category="Financial",
            source_file="leadership_kpis.xlsx",
        ),
        BusinessMetric(
            id="m-002",
            collection_id=seeded_collection.id,
            metric_name="Headcount",
            metric_value=342.0,
            unit="employees",
            period="2025-Q4",
            category="HR",
            source_file="leadership_kpis.xlsx",
        ),
        BusinessMetric(
            id="m-003",
            collection_id=seeded_collection.id,
            metric_name="NPS Score",
            metric_value=72.0,
            unit="points",
            period="2025-Q4",
            category="Customer",
            source_file="leadership_kpis.xlsx",
        ),
        BusinessMetric(
            id="m-004",
            collection_id=seeded_collection.id,
            metric_name="Revenue",
            metric_value=1100000.0,
            unit="USD",
            period="2025-Q3",
            category="Financial",
            source_file="leadership_kpis.xlsx",
        ),
    ]
    sqlite_session.add_all(metrics)
    sqlite_session.commit()
    return metrics


@pytest.mark.integration
class TestSqlDataIngestion:
    """Verify structured data can be ingested into business_metrics table."""

    def test_business_metrics_table_created(self, sqlite_engine) -> None:
        from sqlalchemy import inspect as sa_inspect

        inspector = sa_inspect(sqlite_engine)
        table_names = inspector.get_table_names()
        assert "business_metrics" in table_names
        assert "collections" in table_names

    def test_seed_inserts_metrics_into_table(
        self,
        sqlite_session: Session,
        seeded_metrics: list[BusinessMetric],
    ) -> None:
        from sqlalchemy import func, select

        count = sqlite_session.execute(select(func.count(BusinessMetric.id))).scalar_one()
        assert count == 4

    def test_metrics_belong_to_collection(
        self,
        sqlite_session: Session,
        seeded_collection: Collection,
        seeded_metrics: list[BusinessMetric],
    ) -> None:
        from sqlalchemy import select

        metrics = (
            sqlite_session.execute(select(BusinessMetric).where(BusinessMetric.collection_id == seeded_collection.id))
            .scalars()
            .all()
        )
        assert len(metrics) == 4

    def test_metrics_filterable_by_category(
        self,
        sqlite_session: Session,
        seeded_metrics: list[BusinessMetric],
    ) -> None:
        from sqlalchemy import select

        financial = (
            sqlite_session.execute(select(BusinessMetric).where(BusinessMetric.category == "Financial")).scalars().all()
        )
        assert len(financial) == 2

    def test_metrics_filterable_by_period(
        self,
        sqlite_session: Session,
        seeded_metrics: list[BusinessMetric],
    ) -> None:
        from sqlalchemy import select

        q4_metrics = (
            sqlite_session.execute(select(BusinessMetric).where(BusinessMetric.period == "2025-Q4")).scalars().all()
        )
        assert len(q4_metrics) == 3


@pytest.mark.integration
class TestSqlQueryEngine:
    """Verify NLSQLTableQueryEngine can query structured business data."""

    def test_create_sql_database_wraps_engine(self, sqlite_engine) -> None:
        from llama_index.core import SQLDatabase

        sql_db = SQLDatabase(
            sqlite_engine,
            include_tables=["business_metrics"],
            sample_rows_in_table_info=3,
        )
        usable = sql_db.get_usable_table_names()
        assert "business_metrics" in usable

    def test_sql_database_includes_both_structured_tables(self, sqlite_engine) -> None:
        """Dual-schema pattern: both business_metrics and collections are queryable."""
        from llama_index.core import SQLDatabase

        sql_db = SQLDatabase(
            sqlite_engine,
            include_tables=["business_metrics", "collections"],
            sample_rows_in_table_info=3,
        )
        usable = sql_db.get_usable_table_names()
        assert "business_metrics" in usable
        assert "collections" in usable

    def test_sql_database_table_info_contains_column_names(self, sqlite_engine) -> None:
        from llama_index.core import SQLDatabase

        sql_db = SQLDatabase(
            sqlite_engine,
            include_tables=["business_metrics"],
        )
        table_info = sql_db.get_single_table_info("business_metrics")
        assert "metric_name" in table_info
        assert "metric_value" in table_info
        assert "collection_id" in table_info
        assert "period" in table_info

    @patch("backend.src.tools.sql_tool.create_sql_database")
    def test_execute_sql_query_returns_structured_result(
        self,
        mock_create_db: MagicMock,
    ) -> None:
        from backend.src.models.domain import SqlQueryResult
        from backend.src.tools.sql_tool import execute_sql_query

        mock_response = MagicMock()
        mock_response.__str__ = lambda self: "Q4 revenue is $1,250,000"
        mock_response.metadata = {
            "sql_query": ("SELECT metric_value FROM business_metrics WHERE metric_name='Revenue' AND period='2025-Q4'"),
        }

        mock_engine = MagicMock()
        mock_engine.query.return_value = mock_response
        mock_create_db.return_value = MagicMock()

        with patch(
            "backend.src.tools.sql_tool.NLSQLTableQueryEngine",
            return_value=mock_engine,
        ):
            settings = MagicMock()
            result = execute_sql_query("What is Q4 revenue?", settings)

        assert isinstance(result, SqlQueryResult)
        assert "1,250,000" in result.answer
        assert "SELECT" in result.sql_query


@pytest.mark.integration
class TestSqlCollectionFiltering:
    """Verify SQL queries can filter by collection — dual-schema pattern.

    Like talk2data's sql_schema, our structured tables support collection-based
    filtering via the collection_id foreign key.
    """

    def test_query_metrics_by_collection_id(
        self,
        sqlite_session: Session,
        seeded_collection: Collection,
        seeded_metrics: list[BusinessMetric],
    ) -> None:
        from sqlalchemy import select

        result = sqlite_session.execute(
            select(BusinessMetric.metric_name, BusinessMetric.metric_value)
            .where(BusinessMetric.collection_id == seeded_collection.id)
            .where(BusinessMetric.metric_name == "Revenue")
            .where(BusinessMetric.period == "2025-Q4")
        ).first()

        assert result is not None
        assert result[0] == "Revenue"
        assert result[1] == 1250000.0

    def test_different_collections_isolate_data(
        self,
        sqlite_session: Session,
        seeded_collection: Collection,
        seeded_metrics: list[BusinessMetric],
    ) -> None:
        """Metrics from one collection should not appear in another collection's queries."""
        other_collection = Collection(
            id="test-col-002",
            name="engineering",
            description="Engineering metrics",
            vector_table="vec_engineering",
        )
        sqlite_session.add(other_collection)
        sqlite_session.commit()

        from sqlalchemy import func, select

        other_count = sqlite_session.execute(
            select(func.count(BusinessMetric.id)).where(BusinessMetric.collection_id == other_collection.id)
        ).scalar_one()
        assert other_count == 0

        leadership_count = sqlite_session.execute(
            select(func.count(BusinessMetric.id)).where(BusinessMetric.collection_id == seeded_collection.id)
        ).scalar_one()
        assert leadership_count == 4


@pytest.mark.integration
class TestExcelToSqlPipeline:
    """Verify end-to-end Excel ingestion into structured tables."""

    def test_ingest_excel_creates_business_metrics(
        self,
        sqlite_session: Session,
        seeded_collection: Collection,
        tmp_path,
    ) -> None:
        from openpyxl import Workbook

        from backend.src.ingestion.excel_parser import ingest_excel_to_business_metrics

        wb = Workbook()
        ws = wb.active
        ws.append(["metric_name", "metric_value", "unit", "period", "category"])
        ws.append(["Revenue", 500000, "USD", "2025-Q1", "Financial"])
        ws.append(["Headcount", 100, "employees", "2025-Q1", "HR"])
        filepath = tmp_path / "test_kpis.xlsx"
        wb.save(filepath)

        count = ingest_excel_to_business_metrics(filepath, sqlite_session, seeded_collection.id)

        assert count == 2
        from sqlalchemy import func, select

        total = sqlite_session.execute(select(func.count(BusinessMetric.id))).scalar_one()
        assert total == 2

    def test_ingest_excel_empty_file_returns_zero(
        self,
        sqlite_session: Session,
        seeded_collection: Collection,
        tmp_path,
    ) -> None:
        from openpyxl import Workbook

        from backend.src.ingestion.excel_parser import ingest_excel_to_business_metrics

        wb = Workbook()
        ws = wb.active
        ws.append(["metric_name", "metric_value", "unit", "period", "category"])
        filepath = tmp_path / "empty_kpis.xlsx"
        wb.save(filepath)

        count = ingest_excel_to_business_metrics(filepath, sqlite_session, seeded_collection.id)
        assert count == 0
