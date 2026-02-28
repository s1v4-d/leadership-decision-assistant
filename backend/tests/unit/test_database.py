"""Tests for database engine and session management."""

from __future__ import annotations

from unittest.mock import MagicMock

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.src.core.database import create_session_factory, create_sync_engine, create_tables
from backend.src.models.tables import Base


class TestCreateSyncEngine:
    def test_returns_engine_instance(self) -> None:
        settings = _make_settings()
        engine = create_sync_engine(settings)
        assert isinstance(engine, Engine)
        engine.dispose()

    def test_uses_psycopg2_driver(self) -> None:
        settings = _make_settings()
        engine = create_sync_engine(settings)
        assert engine.url.drivername == "postgresql+psycopg2"
        engine.dispose()

    def test_uses_postgres_settings_fields(self) -> None:
        settings = _make_settings(host="db.example.com", port=5433, database="testdb", user="admin")
        engine = create_sync_engine(settings)
        assert engine.url.host == "db.example.com"
        assert engine.url.port == 5433
        assert engine.url.database == "testdb"
        assert engine.url.username == "admin"
        engine.dispose()

    def test_pool_pre_ping_enabled(self) -> None:
        settings = _make_settings()
        engine = create_sync_engine(settings)
        assert engine.pool._pre_ping is True  # noqa: SLF001
        engine.dispose()


class TestCreateTables:
    def test_creates_tables_with_real_sqlite(self) -> None:
        from sqlalchemy import create_engine

        engine = create_engine("sqlite://")
        create_tables(engine)
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        assert "collections" in table_names
        assert "business_metrics" in table_names

    def test_create_tables_is_idempotent(self) -> None:
        from sqlalchemy import create_engine

        engine = create_engine("sqlite://")
        create_tables(engine)
        create_tables(engine)
        inspector = inspect(engine)
        assert "collections" in inspector.get_table_names()


class TestCreateSessionFactory:
    def test_returns_callable(self) -> None:
        from sqlalchemy import create_engine

        engine = create_engine("sqlite://")
        factory = create_session_factory(engine)
        assert callable(factory)

    def test_creates_session_instances(self) -> None:
        from sqlalchemy import create_engine

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        factory = create_session_factory(engine)
        with factory() as session:
            assert isinstance(session, Session)


def _make_settings(
    host: str = "localhost",
    port: int = 5432,
    database: str = "leadership_agent",
    user: str = "leadership",
    password: str = "test-only",  # noqa: S107
) -> MagicMock:
    """Build a mock Settings with nested PostgresSettings."""
    settings = MagicMock()
    settings.postgres.host = host
    settings.postgres.port = port
    settings.postgres.database = database
    settings.postgres.user = user
    settings.postgres.password.get_secret_value.return_value = password
    return settings
