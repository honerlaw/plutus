"""Tests for the live paper runner — focused on wiring, not the loop."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from plutus.runner import build_runner

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_build_runner_wires_enabled_strategies_to_trader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_API_SECRET", "s")
    monkeypatch.setenv("ALPACA_PAPER", "true")
    monkeypatch.setenv("PLUTUS_DB_PATH", str(tmp_path / "db.sqlite"))

    universe = tmp_path / "u.yaml"
    universe.write_text(
        "symbols: [AAPL]\n"
        "strategies:\n"
        "  orb:\n"
        "    enabled: true\n"
        "    risk_per_trade: 0.005\n"
        "    opening_range_minutes: 15\n"
        "  rsi_vwap:\n"
        "    enabled: false\n"
        "  donchian_swing:\n"
        "    enabled: false\n"
    )

    with (
        patch("plutus.runner.make_paper_broker") as mk_broker,
        patch("plutus.runner.Trader") as mk_trader,
        patch("plutus.runner.init_db") as mk_init_db,
        patch("plutus.runner.Session") as mk_session,
    ):
        mock_engine = MagicMock()
        mk_init_db.return_value = mock_engine
        mk_broker.return_value = MagicMock()
        trader_inst = MagicMock()
        mk_trader.return_value = trader_inst
        # Session is used as a context manager; wire up the mock correctly.
        mk_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mk_session.return_value.__exit__ = MagicMock(return_value=False)
        bundle = build_runner(universe_path=universe)

    mk_broker.assert_called_once()
    assert bundle.trader is trader_inst
    assert len(bundle.strategies) == 1
    assert bundle.strategies[0].__class__.__name__ == "OrbStrategy"
    trader_inst.add_strategy.assert_called_once()
