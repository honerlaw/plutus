"""FastAPI web application for the Plutus paper trading lab."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated
from uuid import uuid4

import sqlalchemy.exc
import structlog
import structlog.contextvars
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text as sa_text
from sqlalchemy.engine import Engine, make_url
from sqlmodel import Session, select
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

import plutus.strategies  # noqa: F401 -- registers all strategies
from plutus.config import Settings
from plutus.logging import configure_logging
from plutus.report import build_summary
from plutus.storage import Signal, init_db
from plutus.strategies.registry import REGISTRY

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from starlette.requests import Request
    from starlette.responses import Response

_engine: Engine | None = None
_log = structlog.get_logger()


class _RequestIDMiddleware(BaseHTTPMiddleware):
    """Bind a unique request ID to the structlog context for each request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Bind a unique request_id to structlog contextvars and clear after response."""
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=str(uuid4()))
        try:
            return await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialize the database engine on startup; dispose it on shutdown."""
    global _engine  # noqa: PLW0603
    settings = Settings()
    configure_logging(settings.log_level)
    _engine = init_db(settings.database_url)
    safe_url = make_url(settings.database_url).render_as_string(hide_password=True)
    _log.info("web.startup", database_url=safe_url)
    try:
        yield
    finally:
        if _engine is not None:
            _engine.dispose()
            _engine = None


app = FastAPI(title="Plutus", lifespan=_lifespan)
app.add_middleware(_RequestIDMiddleware)


def _get_session() -> Iterator[Session]:
    """Yield a database session, closing it after the request."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    session = Session(_engine)
    try:
        yield session
    finally:
        session.close()


def _get_engine() -> Engine:
    """Return the shared database engine or raise 503 if not initialized."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    return _engine


# ---- Response models ----


class HealthResponse(BaseModel):
    """Health check response body."""

    status: str
    db: str


class SignalOut(BaseModel):
    """Single signal as returned by the API."""

    id: int | None
    strategy_name: str
    timestamp: datetime
    symbol: str
    side: str
    qty: float
    signal_type: str
    price_at_signal: float


class ReportRow(BaseModel):
    """Per-strategy performance summary row."""

    strategy: str
    signals: int
    filled: int
    avg_slip_bp: float | None


# ---- Dependency aliases ----

_SessionDep = Annotated[Session, Depends(_get_session)]
_EngineDep = Annotated[Engine, Depends(_get_engine)]


# ---- Endpoints ----


@app.get("/health", response_model=HealthResponse)
def health(engine: _EngineDep) -> HealthResponse:
    """Return application and database health status."""
    try:
        with engine.connect() as conn:
            conn.execute(sa_text("SELECT 1"))
        return HealthResponse(status="ok", db="ok")
    except sqlalchemy.exc.SQLAlchemyError as exc:
        _log.warning("web.health.db_error", error=str(exc))
        raise HTTPException(
            status_code=503,
            detail={"status": "error", "db": "unreachable"},
        ) from exc


@app.get("/strategies", response_model=list[str])
def strategies() -> list[str]:
    """Return a sorted list of registered strategy names."""
    return sorted(REGISTRY)


@app.get("/signals", response_model=list[SignalOut])
def signals(
    session: _SessionDep,
    strategy: str | None = None,
    since: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[SignalOut]:
    """Return recent trading signals, newest first.

    Args:
        session: Database session (injected).
        strategy: Optional strategy-name filter.
        since: Earliest timestamp (ISO 8601). Defaults to 7 days ago.
        limit: Maximum rows to return (1-500, default 100).
    """
    cutoff = since or (datetime.now(UTC) - timedelta(days=7))
    stmt = select(Signal).where(Signal.timestamp >= cutoff)
    if strategy is not None:
        stmt = stmt.where(Signal.strategy_name == strategy)
    rows = session.exec(  # type: ignore[call-overload]
        stmt.order_by(Signal.timestamp.desc()).limit(limit)  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
    ).all()
    return [SignalOut.model_validate(r.model_dump()) for r in rows]


@app.get("/report", response_model=list[ReportRow])
def report(
    engine: _EngineDep,
    since: datetime | None = None,
) -> list[ReportRow]:
    """Return per-strategy performance summary.

    Args:
        engine: Database engine (injected).
        since: Start of reporting window (ISO 8601). Defaults to 30 days ago.
    """
    cutoff = since or (datetime.now(UTC) - timedelta(days=30))
    rows = build_summary(engine, since=cutoff)
    return [
        ReportRow(
            strategy=r.strategy,
            signals=r.signals,
            filled=r.filled,
            avg_slip_bp=r.avg_slip_bp,
        )
        for r in rows
    ]
