"""Tests for the FastAPI web layer."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from plutus.storage.models import Order, Run, Signal
from plutus.web import _get_engine, _get_session, app

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.engine import Engine


@pytest.fixture
def db_engine() -> Generator[Engine]:
    """Yield a fresh in-memory SQLite engine with all tables created."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(db_engine: Engine) -> Generator[TestClient]:
    """Yield a TestClient with get_session and get_engine overridden."""
    mp = pytest.MonkeyPatch()
    mp.setenv("ALPACA_API_KEY", "k")
    mp.setenv("ALPACA_API_SECRET", "s")
    mp.setenv("PLUTUS_DB_URL", "sqlite:///:memory:")

    def override_session() -> Generator[Session]:
        session = Session(db_engine)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[_get_session] = override_session
    app.dependency_overrides[_get_engine] = lambda: db_engine
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    mp.undo()


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] == "ok"


def test_strategies_returns_registered_strategies(client: TestClient) -> None:
    response = client.get("/strategies")
    assert response.status_code == 200
    names = response.json()
    assert "orb" in names
    assert "rsi_vwap" in names
    assert "donchian_swing" in names


def test_signals_returns_empty_list_when_no_data(client: TestClient) -> None:
    response = client.get("/signals")
    assert response.status_code == 200
    assert response.json() == []


def test_signals_returns_recent_signals(client: TestClient, db_engine: Engine) -> None:
    run_id = uuid4()
    with Session(db_engine) as s:
        s.add(
            Run(
                id=run_id,
                strategy_name="orb",
                mode="paper",
                started_at=datetime.now(UTC),
                config_json="{}",
            )
        )
        s.add(
            Signal(
                run_id=run_id,
                strategy_name="orb",
                timestamp=datetime.now(UTC),
                symbol="AAPL",
                side="buy",
                qty=10.0,
                signal_type="entry",
                price_at_signal=200.0,
                indicator_values_json=json.dumps({}),
            )
        )
        s.commit()

    response = client.get("/signals")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["strategy_name"] == "orb"
    assert rows[0]["symbol"] == "AAPL"


def test_signals_filters_by_strategy(client: TestClient, db_engine: Engine) -> None:
    run_id = uuid4()
    with Session(db_engine) as s:
        s.add(
            Run(
                id=run_id,
                strategy_name="orb",
                mode="paper",
                started_at=datetime.now(UTC),
                config_json="{}",
            )
        )
        for strat in ["orb", "rsi_vwap"]:
            s.add(
                Signal(
                    run_id=run_id,
                    strategy_name=strat,
                    timestamp=datetime.now(UTC),
                    symbol="SPY",
                    side="buy",
                    qty=1.0,
                    signal_type="entry",
                    price_at_signal=500.0,
                    indicator_values_json="{}",
                )
            )
        s.commit()

    response = client.get("/signals?strategy=orb")
    assert response.status_code == 200
    rows = response.json()
    assert all(r["strategy_name"] == "orb" for r in rows)
    assert len(rows) == 1


def test_signals_limit_param(client: TestClient, db_engine: Engine) -> None:
    run_id = uuid4()
    with Session(db_engine) as s:
        s.add(
            Run(
                id=run_id,
                strategy_name="orb",
                mode="paper",
                started_at=datetime.now(UTC),
                config_json="{}",
            )
        )
        for _ in range(5):
            s.add(
                Signal(
                    run_id=run_id,
                    strategy_name="orb",
                    timestamp=datetime.now(UTC),
                    symbol="AAPL",
                    side="buy",
                    qty=1.0,
                    signal_type="entry",
                    price_at_signal=200.0,
                    indicator_values_json="{}",
                )
            )
        s.commit()

    response = client.get("/signals?limit=2")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_signals_limit_max_enforced(client: TestClient) -> None:
    response = client.get("/signals?limit=9999")
    assert response.status_code == 422


def test_health_returns_503_when_db_unreachable(
    client: TestClient,
    db_engine: Engine,
) -> None:
    from unittest.mock import MagicMock

    broken = MagicMock()
    broken.connect.return_value.__enter__.side_effect = Exception("connection refused")
    app.dependency_overrides[_get_engine] = lambda: broken
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides[_get_engine] = lambda: db_engine
    assert response.status_code == 503


def test_report_returns_empty_when_no_data(client: TestClient) -> None:
    response = client.get("/report")
    assert response.status_code == 200
    assert response.json() == []


def test_report_returns_summary(client: TestClient, db_engine: Engine) -> None:
    run_id = uuid4()
    with Session(db_engine) as s:
        s.add(
            Run(
                id=run_id,
                strategy_name="orb",
                mode="paper",
                started_at=datetime.now(UTC),
                config_json="{}",
            )
        )
        sig = Signal(
            run_id=run_id,
            strategy_name="orb",
            timestamp=datetime.now(UTC),
            symbol="AAPL",
            side="buy",
            qty=10.0,
            signal_type="entry",
            price_at_signal=200.0,
            indicator_values_json="{}",
        )
        s.add(sig)
        s.commit()
        s.refresh(sig)
        assert sig.id is not None
        s.add(
            Order(
                run_id=run_id,
                signal_id=sig.id,
                status="filled",
                filled_price=200.5,
                filled_qty=10.0,
                submitted_at=datetime.now(UTC),
            )
        )
        s.commit()

    response = client.get("/report")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["strategy"] == "orb"
    assert rows[0]["signals"] == 1
    assert rows[0]["filled"] == 1
