"""Shared pytest fixtures and configuration."""

import pytest

from backend.src.core.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """Clear the lru_cache on get_settings before each test."""
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    """Reset the SlowAPI rate limiter state between tests."""
    from backend.src.api.query_routes import limiter

    limiter.reset()
