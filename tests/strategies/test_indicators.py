"""Tests for strategy indicator helpers."""

from __future__ import annotations

import pytest

from plutus.strategies.indicators import atr, donchian, rsi, vwap


def test_rsi_constant_series_returns_50_or_nan() -> None:
    closes = [100.0] * 20
    val = rsi(closes, period=14)
    # all-zero diffs -> avg_gain=0, avg_loss=0 -> conventional 50 (neutral)
    assert val == pytest.approx(50.0)


def test_rsi_uptrend_above_70() -> None:
    closes = [float(i) for i in range(1, 30)]
    assert rsi(closes, period=14) > 70.0


def test_rsi_downtrend_below_30() -> None:
    closes = [float(i) for i in range(30, 1, -1)]
    assert rsi(closes, period=14) < 30.0


def test_vwap_simple() -> None:
    highs = [10.0, 11.0, 12.0]
    lows = [9.0, 10.0, 11.0]
    closes = [9.5, 10.5, 11.5]
    volumes = [100.0, 100.0, 100.0]
    v = vwap(highs, lows, closes, volumes)
    # typical price = (h+l+c)/3 = 9.5,10.5,11.5; vol-weighted mean = 10.5
    assert v == pytest.approx(10.5)


def test_donchian_returns_high_low_of_window() -> None:
    highs = [1.0, 2.0, 3.0, 4.0, 5.0]
    lows = [0.5, 1.5, 2.5, 3.5, 4.5]
    hi, lo = donchian(highs, lows, period=3)
    # last 3 highs: 3,4,5 -> 5; last 3 lows: 2.5,3.5,4.5 -> 2.5
    assert hi == 5.0
    assert lo == 2.5


def test_atr_positive() -> None:
    highs = [10.0, 11.0, 12.0, 11.5, 13.0] * 4
    lows = [9.0, 10.0, 11.0, 10.5, 12.0] * 4
    closes = [9.5, 10.5, 11.5, 11.0, 12.5] * 4
    val = atr(highs, lows, closes, period=14)
    assert val > 0.0


def test_rsi_raises_if_too_few_data() -> None:
    with pytest.raises(ValueError, match="need at least"):
        rsi([1.0, 2.0], period=14)
