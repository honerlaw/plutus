"""Tests for the PlutusStrategy base class — focusing on the signal recorder logic."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlmodel import Session, select

from plutus.storage import Order, Run, Signal, init_db
from plutus.strategies.base import ProposedSignal, SignalRecorder

if TYPE_CHECKING:
    from pathlib import Path


def test_recorder_writes_signal_and_skipped_order_when_submit_disabled(
    tmp_path: Path,
) -> None:
    engine = init_db(tmp_path / "t.db")
    try:
        run_id = uuid4()
        with Session(engine) as s:
            s.add(
                Run(
                    id=run_id,
                    strategy_name="orb",
                    mode="paper",
                    started_at=datetime.now(UTC),
                    config_json="{}",
                )
            )
            s.commit()

        rec = SignalRecorder(engine=engine, run_id=run_id, strategy_name="orb", submit=False)
        proposed = ProposedSignal(
            timestamp=datetime.now(UTC),
            symbol="AAPL",
            side="buy",
            qty=10.0,
            signal_type="entry",
            price_at_signal=200.0,
            stop_price=195.0,
            take_profit_price=210.0,
            indicator_values={"or_high": 201.0, "or_low": 199.0},
        )

        def fake_submit(_p: ProposedSignal) -> str:
            msg = "should not be called when submit=False"
            raise AssertionError(msg)

        rec.record(proposed, submit_fn=fake_submit)

        with Session(engine) as s:
            signals = s.exec(select(Signal)).all()
            orders = s.exec(select(Order)).all()
        assert len(signals) == 1
        assert signals[0].symbol == "AAPL"
        assert len(orders) == 1
        assert orders[0].status == "skipped"
        assert orders[0].alpaca_order_id is None
    finally:
        engine.dispose()


def test_recorder_calls_submit_and_records_alpaca_id_when_enabled(
    tmp_path: Path,
) -> None:
    engine = init_db(tmp_path / "t2.db")
    try:
        run_id = uuid4()
        with Session(engine) as s:
            s.add(
                Run(
                    id=run_id,
                    strategy_name="orb",
                    mode="paper",
                    started_at=datetime.now(UTC),
                    config_json="{}",
                )
            )
            s.commit()

        rec = SignalRecorder(engine=engine, run_id=run_id, strategy_name="orb", submit=True)
        proposed = ProposedSignal(
            timestamp=datetime.now(UTC),
            symbol="MSFT",
            side="sell",
            qty=5.0,
            signal_type="exit",
            price_at_signal=400.0,
            stop_price=None,
            take_profit_price=None,
            indicator_values={},
        )

        def fake_submit(_p: ProposedSignal) -> str:
            return "alpaca-xyz"

        rec.record(proposed, submit_fn=fake_submit)

        with Session(engine) as s:
            orders = s.exec(select(Order)).all()
        assert orders[0].alpaca_order_id == "alpaca-xyz"
        assert orders[0].status == "submitted"
    finally:
        engine.dispose()
