"""Database engine and session management for structured data."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from llama_index.core import SQLDatabase
from sqlalchemy import create_engine as sa_create_engine
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session, sessionmaker

from backend.src.models.tables import Base

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

    from backend.src.core.config import Settings

logger = structlog.get_logger(__name__)

_DEFAULT_STRUCTURED_TABLES = ["business_metrics", "collections"]


def create_sync_engine(settings: Settings) -> Engine:
    """Create a synchronous SQLAlchemy engine from PostgresSettings."""
    pg = settings.postgres
    url = f"postgresql+psycopg2://{pg.user}:{pg.password.get_secret_value()}@{pg.host}:{pg.port}/{pg.database}"
    return sa_create_engine(url, pool_pre_ping=True)


def create_tables(engine: Engine, settings: Settings | None = None) -> None:
    """Create all ORM tables idempotently via metadata.create_all.

    When *settings* is provided the tables are placed into the configured
    ``sql_schema`` (default ``structured``), keeping structured business
    data separate from vector tables.
    """
    if settings is not None:
        Base.metadata.schema = settings.postgres.sql_schema
    Base.metadata.create_all(engine)
    logger.info("structured_tables_created", schema=Base.metadata.schema)


def ensure_schemas(engine: Engine, settings: Settings) -> None:
    """Create the vector_store and structured PostgreSQL schemas if they don't exist.

    This mirrors the talk2data dual-schema pattern where vector and structured
    data live in separate namespaces within the same database.
    """
    schemas = [settings.postgres.vector_schema, settings.postgres.sql_schema]
    with engine.connect() as conn:
        for schema in schemas:
            conn.execute(sa_text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        conn.commit()
    logger.info("database_schemas_ensured", schemas=schemas)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a sessionmaker bound to the given engine."""
    return sessionmaker(bind=engine)


def create_sql_database(
    settings: Settings,
    *,
    include_tables: list[str] | None = None,
) -> SQLDatabase:
    """Create a LlamaIndex SQLDatabase wrapping the structured PostgreSQL tables.

    Uses a dedicated PostgreSQL schema (default: ``structured``) so that
    business-metric tables live in a separate namespace from vector tables.
    """
    engine = create_sync_engine(settings)
    return SQLDatabase(
        engine,
        schema=settings.postgres.sql_schema,
        include_tables=include_tables or _DEFAULT_STRUCTURED_TABLES,
        sample_rows_in_table_info=3,
    )
