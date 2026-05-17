"""Smoke tests for the typer CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from plutus.cli import app

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_list_command_includes_registered_strategies() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "orb" in result.output
    assert "rsi_vwap" in result.output
    assert "donchian_swing" in result.output


def test_signals_command_handles_empty_db(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_API_SECRET", "s")
    monkeypatch.setenv("PLUTUS_DB_PATH", str(tmp_path / "x.db"))
    runner = CliRunner()
    result = runner.invoke(app, ["signals"])
    assert result.exit_code == 0
    assert "no signals" in result.output.lower()


def test_report_command_handles_empty_db(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_API_SECRET", "s")
    monkeypatch.setenv("PLUTUS_DB_PATH", str(tmp_path / "x.db"))
    runner = CliRunner()
    result = runner.invoke(app, ["report"])
    assert result.exit_code == 0
