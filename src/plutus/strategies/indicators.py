"""Pure-function technical indicators used by plutus strategies."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def rsi(closes: Sequence[float], period: int = 14) -> float:
    """Wilder's RSI on the most recent `period+1` closes."""
    if len(closes) < period + 1:
        msg = f"rsi: need at least {period + 1} closes, got {len(closes)}"
        raise ValueError(msg)

    diffs = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in diffs]
    losses = [max(-d, 0.0) for d in diffs]

    # Initial average over the first `period` diffs
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Wilder smoothing for the remainder
    for i in range(period, len(diffs)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0.0 and avg_gain == 0.0:
        return 50.0
    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def vwap(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
) -> float:
    """Volume-weighted average price across the given bars (typical-price method)."""
    if not (len(highs) == len(lows) == len(closes) == len(volumes)):
        msg = "vwap: input sequences must be equal length"
        raise ValueError(msg)
    if not highs:
        msg = "vwap: empty input"
        raise ValueError(msg)

    total_vol = sum(volumes)
    if total_vol == 0.0:
        msg = "vwap: total volume is zero"
        raise ValueError(msg)

    tp_vol = sum(
        ((h + lo + c) / 3.0) * v for h, lo, c, v in zip(highs, lows, closes, volumes, strict=True)
    )
    return tp_vol / total_vol


def donchian(
    highs: Sequence[float],
    lows: Sequence[float],
    period: int,
) -> tuple[float, float]:
    """Return (channel_high, channel_low) over the last `period` bars."""
    if len(highs) < period or len(lows) < period:
        msg = f"donchian: need at least {period} bars"
        raise ValueError(msg)
    return max(highs[-period:]), min(lows[-period:])


def atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> float:
    """Average True Range over the last `period+1` bars, Wilder smoothing."""
    if len(highs) < period + 1:
        msg = f"atr: need at least {period + 1} bars"
        raise ValueError(msg)
    trs: list[float] = []
    for i in range(1, len(highs)):
        prev_close = closes[i - 1]
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - prev_close),
            abs(lows[i] - prev_close),
        )
        trs.append(tr)

    smoothed = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        smoothed = (smoothed * (period - 1) + trs[i]) / period
    return smoothed
