"""NL2SQL query engine tool for structured data retrieval."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from llama_index.core.query_engine import NLSQLTableQueryEngine
from llama_index.core.tools import QueryEngineTool

from backend.src.core.database import create_sql_database
from backend.src.models.domain import SqlQueryResult

if TYPE_CHECKING:
    from backend.src.core.config import Settings

logger = structlog.get_logger(__name__)

_DEFAULT_SQL_TABLES = ["business_metrics"]

SQL_TOOL_DESCRIPTION = (
    "Query structured business data (KPIs, metrics, financial figures) "
    "stored in SQL tables. Use for questions about specific numbers, "
    "trends, comparisons, or any quantitative data."
)


def create_sql_query_engine(
    settings: Settings,
    *,
    tables: list[str] | None = None,
) -> NLSQLTableQueryEngine:
    """Build a NLSQLTableQueryEngine from the structured PostgreSQL tables."""
    sql_database = create_sql_database(settings)
    return NLSQLTableQueryEngine(
        sql_database=sql_database,
        tables=tables or _DEFAULT_SQL_TABLES,
        synthesize_response=True,
    )


def execute_sql_query(query_text: str, settings: Settings) -> SqlQueryResult:
    """Run a natural-language-to-SQL query and return structured results."""
    try:
        engine = create_sql_query_engine(settings)
        response = engine.query(query_text)

        sql_query = response.metadata.get("sql_query", "") if response.metadata else ""

        logger.info("sql_query_executed", sql_query=sql_query)
        return SqlQueryResult(answer=str(response), sql_query=sql_query)
    except Exception as exc:
        logger.exception("sql_query_failed", error=str(exc))
        return SqlQueryResult(
            answer=f"SQL query failed: {exc}",
            sql_query="",
        )


def create_sql_query_tool(settings: Settings) -> QueryEngineTool:
    """Create a QueryEngineTool wrapping the NL2SQL engine for agent integration."""
    engine = create_sql_query_engine(settings)
    return QueryEngineTool.from_defaults(
        query_engine=engine,
        name="structured_query",
        description=SQL_TOOL_DESCRIPTION,
    )
