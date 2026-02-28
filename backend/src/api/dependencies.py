"""FastAPI dependency injection providers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from backend.src.core.config import Settings, get_settings

if TYPE_CHECKING:
    from collections.abc import Generator


SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_session(request: Request) -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session from the app-level session factory."""
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
