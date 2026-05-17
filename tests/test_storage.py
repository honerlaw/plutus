"""Tests for plutus.storage."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlmodel import Session, SQLModel, create_engine, select

from plutus.storage.db import init_db, session_scope
from plutus.storage.models import DailyRunSummary, Order, Run, Signal

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy import Engine


def _engine() -> Engine:
    eng = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(eng)
    return eng


def test_run_round_trip() -> None:
    eng = _engine()
    try:
        run = Run(
            id=uuid4(),
            strategy_name="orb",
            mode="paper",
            started_at=datetime.now(UTC),
            ended_at=None,
            config_json="{}",
        )
        with Session(eng) as s:
            s.add(run)
            s.commit()
            rows = s.exec(select(Run)).all()
        assert len(rows) == 1
        assert rows[0].strategy_name == "orb"
    finally:
        eng.dispose()


def test_signal_and_order_relationship() -> None:
    eng = _engine()
    try:
        run_id = uuid4()
        with Session(eng) as s:
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
                stop_price=195.0,
                take_profit_price=210.0,
                indicator_values_json=json.dumps({"or_high": 201.0}),
            )
            s.add(sig)
            s.commit()
            s.refresh(sig)
            assert sig.id is not None
            sig_id = sig.id
            order = Order(
                run_id=run_id,
                signal_id=sig_id,
                alpaca_order_id="abc",
                status="filled",
                filled_price=200.5,
                filled_qty=10.0,
                submitted_at=datetime.now(UTC),
                filled_at=datetime.now(UTC),
            )
            s.add(order)
            s.commit()
            orders = s.exec(select(Order)).all()
            order_signal_id = orders[0].signal_id
        assert order_signal_id == sig_id
    finally:
        eng.dispose()


def test_daily_run_summary() -> None:
    eng = _engine()
    try:
        run_id = uuid4()
        with Session(eng) as s:
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
                DailyRunSummary(
                    run_id=run_id,
                    strategy_name="orb",
                    trading_date=date(2026, 5, 17),
                    signals_count=5,
                    orders_filled_count=4,
                    realized_pnl=123.45,
                    open_positions_count=1,
                )
            )
            s.commit()
            rows = s.exec(select(DailyRunSummary)).all()
        assert rows[0].realized_pnl == 123.45
    finally:
        eng.dispose()


def test_init_db_creates_tables(tmp_path: Path) -> None:
    db_file = tmp_path / "x.db"
    engine = init_db(db_file)
    try:
        assert db_file.exists()
        # Engine works for a basic insert
        with Session(engine) as s:
            s.add(
                Run(
                    id=uuid4(),
                    strategy_name="orb",
                    mode="paper",
                    started_at=datetime.now(UTC),
                    config_json="{}",
                )
            )
            s.commit()
    finally:
        engine.dispose()


def test_session_scope_commits_on_exit(tmp_path: Path) -> None:
    db_file = tmp_path / "y.db"
    engine = init_db(db_file)
    try:
        rid = uuid4()
        with session_scope(engine) as s:
            s.add(
                Run(
                    id=rid,
                    strategy_name="orb",
                    mode="paper",
                    started_at=datetime.now(UTC),
                    config_json="{}",
                )
            )
        with Session(engine) as s:
            got = s.get(Run, rid)
        assert got is not None
    finally:
        engine.dispose()
