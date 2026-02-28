"""Database engine and session management for structured data."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from llama_index.core import SQLDatabase
from sqlalchemy import create_engine as sa_create_engine
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


def create_tables(engine: Engine) -> None:
    """Create all ORM tables idempotently via metadata.create_all."""
    Base.metadata.create_all(engine)
    logger.info("structured_tables_created")


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a sessionmaker bound to the given engine."""
    return sessionmaker(bind=engine)


def create_sql_database(
    settings: Settings,
    *,
    include_tables: list[str] | None = None,
) -> SQLDatabase:
    """Create a LlamaIndex SQLDatabase wrapping the structured PostgreSQL tables."""
    engine = create_sync_engine(settings)
    return SQLDatabase(
        engine,
        include_tables=include_tables or _DEFAULT_STRUCTURED_TABLES,
        sample_rows_in_table_info=3,
    )
