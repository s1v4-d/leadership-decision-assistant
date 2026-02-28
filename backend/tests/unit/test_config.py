"""Tests for application configuration via Pydantic Settings v2."""

from __future__ import annotations

from unittest.mock import patch

from pydantic import SecretStr

from backend.src.core.config import (
    Settings,
    get_settings,
)


class TestSettings:
    """Tests for the root Settings class."""

    def test_settings_loads_defaults(self) -> None:
        settings = Settings(
            _env_file=None,
            openai_api_key=SecretStr("sk-test"),
        )
        assert settings.app_name == "leadership-insight-agent"
        assert settings.debug is True
        assert settings.log_level == "DEBUG"
        assert settings.log_format == "console"

    def test_settings_api_defaults(self) -> None:
        settings = Settings(
            _env_file=None,
            openai_api_key=SecretStr("sk-test"),
        )
        assert settings.api_host == "0.0.0.0"  # noqa: S104
        assert settings.api_port == 8000
        assert settings.api_workers == 1

    def test_settings_llm_defaults(self) -> None:
        settings = Settings(
            _env_file=None,
            openai_api_key=SecretStr("sk-test"),
        )
        assert settings.llm_provider == "openai"
        assert settings.llm_model == "gpt-4o-mini"
        assert settings.llm_temperature == 0.1
        assert settings.llm_max_tokens == 4096
        assert settings.llm_request_timeout == 60

    def test_settings_embedding_defaults(self) -> None:
        settings = Settings(
            _env_file=None,
            openai_api_key=SecretStr("sk-test"),
        )
        assert settings.embedding_provider == "openai"
        assert settings.embedding_model == "text-embedding-3-small"
        assert settings.embedding_dimension == 1536

    def test_settings_openai_api_key_is_secret(self) -> None:
        settings = Settings(
            _env_file=None,
            openai_api_key=SecretStr("sk-secret-key"),
        )
        assert isinstance(settings.openai_api_key, SecretStr)
        assert settings.openai_api_key.get_secret_value() == "sk-secret-key"

    def test_settings_override_via_env(self) -> None:
        env = {
            "APP_NAME": "custom-app",
            "DEBUG": "false",
            "LOG_LEVEL": "INFO",
            "OPENAI_API_KEY": "sk-env-key",  # pragma: allowlist secret
        }
        with patch.dict("os.environ", env, clear=False):
            settings = Settings(_env_file=None)
            assert settings.app_name == "custom-app"
            assert settings.debug is False
            assert settings.log_level == "INFO"

    def test_settings_cors_origins_parsing(self) -> None:
        settings = Settings(
            _env_file=None,
            openai_api_key=SecretStr("sk-test"),
        )
        assert settings.cors_origins == "http://localhost:8501,http://localhost:3000"


class TestRedisSettings:
    """Tests for Redis nested settings."""

    def test_redis_defaults(self) -> None:
        settings = Settings(
            _env_file=None,
            openai_api_key=SecretStr("sk-test"),
        )
        assert settings.redis.url == "redis://localhost:6379/0"
        assert settings.redis.ttl_seconds == 3600

    def test_redis_override_via_nested_env(self) -> None:
        env = {
            "REDIS__URL": "redis://redis-prod:6379/1",
            "REDIS__TTL_SECONDS": "7200",
            "OPENAI_API_KEY": "sk-test",  # pragma: allowlist secret
        }
        with patch.dict("os.environ", env, clear=False):
            settings = Settings(_env_file=None)
            assert settings.redis.url == "redis://redis-prod:6379/1"
            assert settings.redis.ttl_seconds == 7200


class TestPostgresSettings:
    """Tests for Postgres nested settings."""

    def test_postgres_defaults(self) -> None:
        settings = Settings(
            _env_file=None,
            openai_api_key=SecretStr("sk-test"),
        )
        assert settings.postgres.host == "localhost"
        assert settings.postgres.port == 5432
        assert settings.postgres.user == "leadership"
        assert settings.postgres.password.get_secret_value() == "leadership_dev_password"
        assert settings.postgres.database == "leadership_agent"
        assert settings.postgres.vector_table == "document_vectors"

    def test_postgres_dsn(self) -> None:
        settings = Settings(
            _env_file=None,
            openai_api_key=SecretStr("sk-test"),
        )
        dsn = settings.postgres.dsn
        assert dsn.startswith("postgresql+asyncpg://")
        assert "leadership" in dsn
        assert "localhost" in dsn
        assert "5432" in dsn
        assert "leadership_agent" in dsn


class TestRAGSettings:
    """Tests for RAG nested settings."""

    def test_rag_defaults(self) -> None:
        settings = Settings(
            _env_file=None,
            openai_api_key=SecretStr("sk-test"),
        )
        assert settings.rag.chunk_size == 512
        assert settings.rag.chunk_overlap == 50
        assert settings.rag.similarity_top_k == 5
        assert settings.rag.rerank_top_n == 3
        assert settings.rag.response_mode == "tree_summarize"


class TestSecuritySettings:
    """Tests for Security nested settings."""

    def test_security_defaults(self) -> None:
        settings = Settings(
            _env_file=None,
            openai_api_key=SecretStr("sk-test"),
        )
        assert settings.security.rate_limit == "20/minute"
        assert settings.security.max_query_length == 2000
        assert settings.security.enable_pii_masking is True
        assert settings.security.blocked_patterns == ""


class TestGetSettings:
    """Tests for the get_settings singleton."""

    def test_get_settings_returns_settings_instance(self) -> None:
        env = {"OPENAI_API_KEY": "sk-test"}  # pragma: allowlist secret
        with patch.dict("os.environ", env, clear=False):
            get_settings.cache_clear()
            settings = get_settings()
            assert isinstance(settings, Settings)

    def test_get_settings_returns_cached_instance(self) -> None:
        env = {"OPENAI_API_KEY": "sk-test"}  # pragma: allowlist secret
        with patch.dict("os.environ", env, clear=False):
            get_settings.cache_clear()
            first = get_settings()
            second = get_settings()
            assert first is second
