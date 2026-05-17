"""Tests for the RSI+VWAP strategy pure signal layer."""

from __future__ import annotations

from datetime import UTC, datetime

from plutus.strategies.rsi_vwap import RsiVwapConfig, RsiVwapState, compute_rsi_vwap_signals


def _ts(hour: int, minute: int) -> datetime:
    return datetime(2026, 5, 18, hour, minute, tzinfo=UTC)


def _bars(n: int, close: float = 100.0) -> list[tuple[float, float, float, float, float]]:
    """Return n identical bars as (high, low, open, close, volume)."""
    return [(close + 0.5, close - 0.5, close, close, 1000.0)] * n


def test_long_when_rsi_below_threshold_and_price_below_vwap() -> None:
    cfg = RsiVwapConfig(
        rsi_period=14,
        rsi_long_threshold=30.0,
        rsi_short_threshold=70.0,
        atr_period=14,
        atr_multiplier=1.5,
        risk_per_trade=0.005,
    )
    state = RsiVwapState()
    # Construct closes that produce RSI < 30: monotonic downtrend
    closes = [float(x) for x in range(40, 10, -1)]  # 30 values, sharp downtrend
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    volumes = [1000.0] * len(closes)
    bars = list(zip(highs, lows, closes, closes, volumes, strict=True))  # open==close ok for test

    sigs = compute_rsi_vwap_signals(
        now=_ts(15, 0),
        symbol="AAPL",
        bars_today=bars,
        last_close=closes[-1],
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    assert len(sigs) == 1
    assert sigs[0].side == "buy"


def test_short_when_rsi_above_threshold_and_price_above_vwap() -> None:
    cfg = RsiVwapConfig(
        rsi_period=14,
        rsi_long_threshold=30.0,
        rsi_short_threshold=70.0,
        atr_period=14,
        atr_multiplier=1.5,
        risk_per_trade=0.005,
    )
    state = RsiVwapState()
    closes = [float(x) for x in range(10, 40)]  # uptrend
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    volumes = [1000.0] * len(closes)
    bars = list(zip(highs, lows, closes, closes, volumes, strict=True))

    sigs = compute_rsi_vwap_signals(
        now=_ts(15, 0),
        symbol="AAPL",
        bars_today=bars,
        last_close=closes[-1],
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    assert len(sigs) == 1
    assert sigs[0].side == "sell"


def test_no_double_entry_while_position_open() -> None:
    cfg = RsiVwapConfig(
        rsi_period=14,
        rsi_long_threshold=30.0,
        rsi_short_threshold=70.0,
        atr_period=14,
        atr_multiplier=1.5,
        risk_per_trade=0.005,
    )
    state = RsiVwapState()
    closes = [float(x) for x in range(40, 10, -1)]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    bars = list(zip(highs, lows, closes, closes, [1000.0] * len(closes), strict=True))

    compute_rsi_vwap_signals(
        now=_ts(15, 0),
        symbol="AAPL",
        bars_today=bars,
        last_close=closes[-1],
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    sigs2 = compute_rsi_vwap_signals(
        now=_ts(15, 5),
        symbol="AAPL",
        bars_today=bars,
        last_close=closes[-1],
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    assert sigs2 == []


def test_exit_when_rsi_crosses_50() -> None:
    cfg = RsiVwapConfig(
        rsi_period=14,
        rsi_long_threshold=30.0,
        rsi_short_threshold=70.0,
        atr_period=14,
        atr_multiplier=1.5,
        risk_per_trade=0.005,
    )
    state = RsiVwapState()
    down_closes = [float(x) for x in range(40, 10, -1)]
    down_bars = list(
        zip(
            [c + 0.5 for c in down_closes],
            [c - 0.5 for c in down_closes],
            down_closes,
            down_closes,
            [1000.0] * len(down_closes),
            strict=True,
        )
    )
    compute_rsi_vwap_signals(
        now=_ts(15, 0),
        symbol="AAPL",
        bars_today=down_bars,
        last_close=down_closes[-1],
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    # Now feed a recovery so RSI > 50
    recovery_closes = down_closes + [float(x) for x in range(11, 40)]
    recovery_bars = list(
        zip(
            [c + 0.5 for c in recovery_closes],
            [c - 0.5 for c in recovery_closes],
            recovery_closes,
            recovery_closes,
            [1000.0] * len(recovery_closes),
            strict=True,
        )
    )
    sigs = compute_rsi_vwap_signals(
        now=_ts(15, 30),
        symbol="AAPL",
        bars_today=recovery_bars,
        last_close=recovery_closes[-1],
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    assert any(s.signal_type == "exit" for s in sigs)
