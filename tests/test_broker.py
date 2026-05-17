"""Tests for the Alpaca paper broker factory."""

from unittest.mock import MagicMock, patch

import pytest

from plutus.broker import make_paper_broker
from plutus.config import Settings


def test_make_paper_broker_uses_paper_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_API_SECRET", "s")
    monkeypatch.setenv("ALPACA_PAPER", "true")
    settings = Settings()

    mock_broker = MagicMock()
    mock_broker.is_paper = True

    with patch("lumibot.brokers.Alpaca") as mock_alpaca_cls:
        mock_alpaca_cls.return_value = mock_broker
        broker = make_paper_broker(settings)

        # Verify Alpaca was constructed with PAPER=True (hard-coded safety requirement)
        call_args = mock_alpaca_cls.call_args
        config_arg: dict[str, object] = call_args[0][0]
        assert config_arg["PAPER"] is True
        assert config_arg["API_KEY"] == "k"
        assert config_arg["API_SECRET"] == "s"

    # Verify the returned broker has is_paper=True
    assert broker.is_paper is True
