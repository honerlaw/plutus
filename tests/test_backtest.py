"""Tests for the backtest entry point — wiring only."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from unittest.mock import patch

from plutus.backtest import run_backtest

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_run_backtest_calls_backtest_with_correct_strategy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_API_SECRET", "s")
    monkeypatch.setenv("PLUTUS_DB_URL", f"sqlite:///{tmp_path / 'bt.db'}")

    universe = tmp_path / "u.yaml"
    universe.write_text(
        "symbols: [AAPL]\n"
        "strategies:\n"
        "  orb:\n"
        "    enabled: true\n"
        "    risk_per_trade: 0.005\n"
        "    opening_range_minutes: 15\n"
    )

    with patch("plutus.backtest._run_alpaca_backtest") as mk_run:
        run_backtest(
            strategy_name="orb",
            start=date(2026, 1, 1),
            end=date(2026, 1, 15),
            universe_path=universe,
        )
    mk_run.assert_called_once()
