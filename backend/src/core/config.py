"""Application configuration via Pydantic Settings v2."""

from functools import lru_cache

from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisSettings(BaseModel):
    """Redis cache connection settings."""

    url: str = "redis://localhost:6379/0"
    ttl_seconds: int = 3600


class PostgresSettings(BaseModel):
    """PostgreSQL database connection settings (structured + pgvector)."""

    host: str = "localhost"
    port: int = 5432
    user: str = "leadership"
    password: SecretStr = SecretStr("leadership_dev_password")
    database: str = "leadership_agent"
    vector_table: str = "document_vectors"

    @property
    def dsn(self) -> str:
        """Build an asyncpg-compatible DSN from individual fields."""
        return (
            f"postgresql+asyncpg://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.database}"
        )


class RAGSettings(BaseModel):
    """RAG pipeline tuning parameters."""

    chunk_size: int = 512
    chunk_overlap: int = 50
    similarity_top_k: int = 5
    rerank_top_n: int = 3
    response_mode: str = "tree_summarize"


class SecuritySettings(BaseModel):
    """Input validation and security settings."""

    rate_limit: str = "20/minute"
    max_query_length: int = 2000
    enable_pii_masking: bool = True
    blocked_patterns: str = ""


class Settings(BaseSettings):
    """Root application settings loaded from environment and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        env_ignore_empty=True,
    )

    app_name: str = "leadership-insight-agent"
    debug: bool = True
    log_level: str = "DEBUG"
    log_format: str = "console"

    api_host: str = "0.0.0.0"  # noqa: S104
    api_port: int = 8000
    api_workers: int = 1
    allowed_hosts: str = "*"
    cors_origins: str = "http://localhost:8501,http://localhost:3000"

    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096
    llm_request_timeout: int = 60

    openai_api_key: SecretStr = SecretStr("sk-change-me")

    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-large"
    embedding_dimension: int = 3072

    redis: RedisSettings = RedisSettings()
    postgres: PostgresSettings = PostgresSettings()
    rag: RAGSettings = RAGSettings()
    security: SecuritySettings = SecuritySettings()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
