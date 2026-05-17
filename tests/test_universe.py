"""Tests for plutus.universe."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from plutus.universe import load_universe

if TYPE_CHECKING:
    from pathlib import Path


def test_load_universe_parses_yaml(tmp_path: Path) -> None:
    cfg = tmp_path / "u.yaml"
    cfg.write_text(
        "symbols: [AAPL, MSFT]\n"
        "strategies:\n"
        "  orb:\n"
        "    enabled: true\n"
        "    risk_per_trade: 0.01\n"
    )
    u = load_universe(cfg)
    assert u["symbols"] == ["AAPL", "MSFT"]
    assert u["strategies"]["orb"]["enabled"] is True
    assert u["strategies"]["orb"]["risk_per_trade"] == 0.01


def test_load_universe_raises_for_non_mapping(tmp_path: Path) -> None:
    cfg = tmp_path / "bad.yaml"
    cfg.write_text("- item1\n- item2\n")
    with pytest.raises(TypeError, match="must be a mapping"):
        load_universe(cfg)
