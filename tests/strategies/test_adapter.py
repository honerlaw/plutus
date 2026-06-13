"""Tests for the lumibot adapter classes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlmodel import Session, select

from plutus.storage import Run, Signal, init_db
from plutus.strategies.adapter import (
    DonchianSwingStrategy,
    OrbStrategy,
    RsiVwapStrategy,
    _PlutusAdapter,
)
from plutus.strategies.base import ProposedSignal
from plutus.strategies.registry import REGISTRY

if TYPE_CHECKING:
    from pathlib import Path


def _make_adapter(
    cls: type[_PlutusAdapter],
    tmp_path: Path,
    **params: float,
) -> _PlutusAdapter:
    engine = init_db(f"sqlite:///{tmp_path / 'a.db'}")
    run_id = uuid4()
    with Session(engine) as s:
        s.add(
            Run(
                id=run_id,
                strategy_name=cls._registry_name,
                mode="paper",
                started_at=datetime.now(UTC),
                config_json="{}",
            )
        )
        s.commit()
    inst = cls(**params)
    inst.attach_engine(engine=engine, run_id=run_id, submit=False)
    return inst


def test_orb_adapter_registers() -> None:
    assert REGISTRY["orb"] is OrbStrategy


def test_rsi_vwap_adapter_registers() -> None:
    assert REGISTRY["rsi_vwap"] is RsiVwapStrategy


def test_donchian_adapter_registers() -> None:
    assert REGISTRY["donchian_swing"] is DonchianSwingStrategy


def test_orb_adapter_writes_signal_through_recorder(tmp_path: Path) -> None:
    inst = _make_adapter(
        OrbStrategy,
        tmp_path,
        opening_range_minutes=15,
        risk_per_trade=0.005,
    )
    sig = ProposedSignal(
        timestamp=datetime.now(UTC),
        symbol="AAPL",
        side="buy",
        qty=10.0,
        signal_type="entry",
        price_at_signal=200.0,
        stop_price=199.0,
        take_profit_price=204.0,
        indicator_values={"or_high": 201.0, "or_low": 199.0},
    )
    inst._record_signal(sig, submit_fn=MagicMock(return_value="x"))
    assert inst._engine is not None
    with Session(inst._engine) as s:
        rows = s.exec(select(Signal)).all()
    assert len(rows) == 1
    assert rows[0].symbol == "AAPL"
    inst._engine.dispose()


def test_rsi_vwap_adapter_instantiates_with_defaults(tmp_path: Path) -> None:
    inst = _make_adapter(RsiVwapStrategy, tmp_path)
    assert isinstance(inst, RsiVwapStrategy)
    assert inst._cfg.rsi_period == 14
    assert inst._engine is not None
    inst._engine.dispose()


def test_donchian_adapter_instantiates_with_defaults(tmp_path: Path) -> None:
    inst = _make_adapter(DonchianSwingStrategy, tmp_path)
    assert isinstance(inst, DonchianSwingStrategy)
    assert inst._cfg.channel_period == 20
    assert inst._engine is not None
    inst._engine.dispose()


def test_record_signal_raises_without_engine() -> None:
    inst = OrbStrategy(opening_range_minutes=15, risk_per_trade=0.005)
    sig = ProposedSignal(
        timestamp=datetime.now(UTC),
        symbol="AAPL",
        side="buy",
        qty=5.0,
        signal_type="entry",
        price_at_signal=200.0,
    )
    with pytest.raises(RuntimeError, match="attach_engine"):
        inst._record_signal(sig, submit_fn=MagicMock())
