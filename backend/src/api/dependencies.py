"""FastAPI dependency injection providers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from backend.src.core.config import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]
