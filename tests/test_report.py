"""Tests for plutus.report."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlmodel import Session, select

from plutus.report import build_summary
from plutus.storage import Order, Run, Signal, init_db

if TYPE_CHECKING:
    from pathlib import Path


def test_build_summary_counts_signals_and_fills(tmp_path: Path) -> None:
    engine = init_db(tmp_path / "r.db")
    try:
        run_id = uuid4()
        now = datetime.now(UTC)
        with Session(engine) as s:
            s.add(
                Run(
                    id=run_id,
                    strategy_name="orb",
                    mode="paper",
                    started_at=now,
                    config_json="{}",
                )
            )
            s.commit()
            # Two signals, one filled
            s.add(
                Signal(
                    run_id=run_id,
                    strategy_name="orb",
                    timestamp=now,
                    symbol="AAPL",
                    side="buy",
                    qty=10.0,
                    signal_type="entry",
                    price_at_signal=200.0,
                    indicator_values_json="{}",
                )
            )
            s.add(
                Signal(
                    run_id=run_id,
                    strategy_name="orb",
                    timestamp=now,
                    symbol="AAPL",
                    side="sell",
                    qty=10.0,
                    signal_type="exit",
                    price_at_signal=205.0,
                    indicator_values_json="{}",
                )
            )
            s.commit()
            sigs = s.exec(select(Signal)).all()
            assert sigs[0].id is not None
            assert sigs[1].id is not None
            s.add(
                Order(
                    run_id=run_id,
                    signal_id=sigs[0].id,
                    alpaca_order_id="a",
                    status="filled",
                    filled_price=200.5,
                    filled_qty=10.0,
                    submitted_at=now,
                    filled_at=now,
                )
            )
            s.add(
                Order(
                    run_id=run_id,
                    signal_id=sigs[1].id,
                    alpaca_order_id=None,
                    status="skipped",
                    submitted_at=now,
                )
            )
            s.commit()

        rows = build_summary(engine, since=now - timedelta(days=1))
        assert len(rows) == 1
        row = rows[0]
        assert row.strategy == "orb"
        assert row.signals == 2
        assert row.filled == 1
        assert row.avg_slip_bp is not None
    finally:
        engine.dispose()
