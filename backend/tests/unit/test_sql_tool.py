"""TDD tests for NL2SQL query engine tool."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.src.core.config import Settings


class TestCreateSqlDatabase:
    """Test create_sql_database() wraps a SQLAlchemy engine for LlamaIndex."""

    @patch("backend.src.core.database.SQLDatabase")
    @patch("backend.src.core.database.create_sync_engine")
    def test_creates_sql_database_with_include_tables(
        self, mock_engine_fn: MagicMock, mock_sql_db_cls: MagicMock
    ) -> None:
        from backend.src.core.database import create_sql_database

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        mock_engine = MagicMock()
        mock_engine_fn.return_value = mock_engine
        mock_sql_db = MagicMock()
        mock_sql_db_cls.return_value = mock_sql_db

        result = create_sql_database(settings, include_tables=["business_metrics"])

        mock_sql_db_cls.assert_called_once_with(
            mock_engine,
            schema="structured",
            include_tables=["business_metrics"],
            sample_rows_in_table_info=3,
        )
        assert result is mock_sql_db

    @patch("backend.src.core.database.SQLDatabase")
    @patch("backend.src.core.database.create_sync_engine")
    def test_creates_sql_database_defaults_to_all_structured_tables(
        self, mock_engine_fn: MagicMock, mock_sql_db_cls: MagicMock
    ) -> None:
        from backend.src.core.database import create_sql_database

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        mock_engine_fn.return_value = MagicMock()
        mock_sql_db_cls.return_value = MagicMock()

        create_sql_database(settings)

        call_kwargs = mock_sql_db_cls.call_args[1]
        assert "business_metrics" in call_kwargs["include_tables"]
        assert "collections" in call_kwargs["include_tables"]


class TestCreateSqlQueryEngine:
    """Test create_sql_query_engine() builds a NLSQLTableQueryEngine."""

    @patch("backend.src.tools.sql_tool.create_sql_database")
    @patch("backend.src.tools.sql_tool.NLSQLTableQueryEngine")
    def test_creates_engine_with_sql_database(self, mock_engine_cls: MagicMock, mock_create_db: MagicMock) -> None:
        from backend.src.tools.sql_tool import create_sql_query_engine

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        mock_db = MagicMock()
        mock_create_db.return_value = mock_db
        mock_engine = MagicMock()
        mock_engine_cls.return_value = mock_engine

        result = create_sql_query_engine(settings)

        mock_create_db.assert_called_once_with(settings)
        mock_engine_cls.assert_called_once_with(
            sql_database=mock_db,
            tables=["business_metrics"],
            synthesize_response=True,
        )
        assert result is mock_engine

    @patch("backend.src.tools.sql_tool.create_sql_database")
    @patch("backend.src.tools.sql_tool.NLSQLTableQueryEngine")
    def test_creates_engine_with_custom_tables(self, mock_engine_cls: MagicMock, mock_create_db: MagicMock) -> None:
        from backend.src.tools.sql_tool import create_sql_query_engine

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        mock_create_db.return_value = MagicMock()
        mock_engine_cls.return_value = MagicMock()

        create_sql_query_engine(settings, tables=["collections", "assets"])

        call_kwargs = mock_engine_cls.call_args[1]
        assert call_kwargs["tables"] == ["collections", "assets"]


class TestExecuteSqlQuery:
    """Test execute_sql_query() runs NL2SQL and returns structured results."""

    @patch("backend.src.tools.sql_tool.create_sql_query_engine")
    def test_returns_sql_query_result_on_success(
        self,
        mock_create_engine: MagicMock,
    ) -> None:
        from backend.src.models.domain import SqlQueryResult
        from backend.src.tools.sql_tool import execute_sql_query

        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        mock_response = MagicMock()
        mock_response.__str__ = MagicMock(return_value="Revenue was $5M in Q4.")
        mock_response.metadata = {
            "sql_query": "SELECT metric_value FROM business_metrics WHERE metric_name = 'revenue'",
        }
        mock_engine.query.return_value = mock_response

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        result = execute_sql_query("What was Q4 revenue?", settings)

        assert isinstance(result, SqlQueryResult)
        assert result.answer == "Revenue was $5M in Q4."
        assert "SELECT" in result.sql_query
        mock_engine.query.assert_called_once_with("What was Q4 revenue?")

    @patch("backend.src.tools.sql_tool.create_sql_query_engine")
    def test_returns_error_result_on_failure(
        self,
        mock_create_engine: MagicMock,
    ) -> None:
        from backend.src.models.domain import SqlQueryResult
        from backend.src.tools.sql_tool import execute_sql_query

        mock_create_engine.side_effect = RuntimeError("connection refused")

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        result = execute_sql_query("What was Q4 revenue?", settings)

        assert isinstance(result, SqlQueryResult)
        assert "connection refused" in result.answer
        assert result.sql_query == ""

    @patch("backend.src.tools.sql_tool.create_sql_query_engine")
    def test_handles_missing_metadata_sql_query(
        self,
        mock_create_engine: MagicMock,
    ) -> None:
        from backend.src.tools.sql_tool import execute_sql_query

        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        mock_response = MagicMock()
        mock_response.__str__ = MagicMock(return_value="Some answer")
        mock_response.metadata = {}
        mock_engine.query.return_value = mock_response

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        result = execute_sql_query("test", settings)

        assert result.answer == "Some answer"
        assert result.sql_query == ""


class TestCreateSqlQueryTool:
    """Test create_sql_query_tool() wraps the engine in a QueryEngineTool."""

    @patch("backend.src.tools.sql_tool.create_sql_query_engine")
    @patch("backend.src.tools.sql_tool.QueryEngineTool")
    def test_creates_tool_with_name_and_description(
        self, mock_tool_cls: MagicMock, mock_create_engine: MagicMock
    ) -> None:
        from backend.src.tools.sql_tool import create_sql_query_tool

        settings = Settings(_env_file=None, openai_api_key="sk-test")
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        mock_tool = MagicMock()
        mock_tool_cls.from_defaults.return_value = mock_tool

        result = create_sql_query_tool(settings)

        mock_tool_cls.from_defaults.assert_called_once()
        call_kwargs = mock_tool_cls.from_defaults.call_args[1]
        assert call_kwargs["query_engine"] is mock_engine
        assert call_kwargs["name"] == "structured_query"
        assert "SQL" in call_kwargs["description"] or "structured" in call_kwargs["description"]
        assert result is mock_tool


class TestSqlQueryResultModel:
    """Test the SqlQueryResult domain model."""

    def test_sql_query_result_has_required_fields(self) -> None:
        from backend.src.models.domain import SqlQueryResult

        result = SqlQueryResult(
            answer="Revenue was $5M.",
            sql_query="SELECT metric_value FROM business_metrics",
        )
        assert result.answer == "Revenue was $5M."
        assert result.sql_query == "SELECT metric_value FROM business_metrics"

    def test_sql_query_result_defaults(self) -> None:
        from backend.src.models.domain import SqlQueryResult

        result = SqlQueryResult(answer="test")
        assert result.sql_query == ""
