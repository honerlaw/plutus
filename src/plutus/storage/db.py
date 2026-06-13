"""Database engine factory and session helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlmodel import Session, SQLModel, create_engine

# Import models so SQLModel.metadata knows about them before create_all.
from plutus.storage import models  # noqa: F401

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.engine import Engine


def init_db(url: str) -> Engine:
    """Create tables (if absent) against the given database URL and return the engine."""
    engine = create_engine(url)
    SQLModel.metadata.create_all(engine)
    return engine


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
