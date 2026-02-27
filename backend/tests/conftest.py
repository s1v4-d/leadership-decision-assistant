"""Shared pytest fixtures and configuration."""

import pytest
from pydantic import SecretStr

from backend.src.core.config import Settings, get_settings


@pytest.fixture()
def test_settings() -> Settings:
    """Provide a Settings instance isolated from real .env files."""
    return Settings(
        _env_file=None,
        openai_api_key=SecretStr("sk-test-fixture"),
    )


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """Clear the lru_cache on get_settings before each test."""
    get_settings.cache_clear()
