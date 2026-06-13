"""Tests for plutus.config."""

from __future__ import annotations

from typing import TYPE_CHECKING

from plutus.config import Settings

if TYPE_CHECKING:
    import pytest


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPACA_API_KEY", "key123")
    monkeypatch.setenv("ALPACA_API_SECRET", "secret456")
    monkeypatch.setenv("ALPACA_PAPER", "true")
    monkeypatch.setenv("PLUTUS_SUBMIT_ORDERS", "false")
    monkeypatch.setenv("PLUTUS_DB_URL", "postgresql://user:pass@localhost/testdb")
    monkeypatch.setenv("PLUTUS_LOG_LEVEL", "DEBUG")

    s = Settings()

    assert s.alpaca_api_key == "key123"
    assert s.alpaca_api_secret == "secret456"
    assert s.alpaca_paper is True
    assert s.submit_orders is False
    assert s.database_url == "postgresql://user:pass@localhost/testdb"
    assert s.log_level == "DEBUG"


def test_settings_paper_is_always_true_even_if_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_API_SECRET", "s")
    monkeypatch.setenv("ALPACA_PAPER", "false")
    monkeypatch.setenv("PLUTUS_DB_URL", "sqlite:///:memory:")

    s = Settings()

    assert s.alpaca_paper is True, "paper trading must be forced on"
