"""RSI(14) + VWAP filter mean-reversion strategy — pure signal logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from plutus.strategies.base import ProposedSignal
from plutus.strategies.indicators import atr, rsi, vwap

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

Bar = tuple[float, float, float, float, float]  # high, low, open, close, volume

_EXIT_RSI = 50.0


@dataclass(frozen=True)
class RsiVwapConfig:
    """Configuration for the RSI+VWAP mean-reversion strategy."""

    rsi_period: int = 14
    rsi_long_threshold: float = 30.0
    rsi_short_threshold: float = 70.0
    atr_period: int = 14
    atr_multiplier: float = 1.5
    risk_per_trade: float = 0.005


@dataclass
class RsiVwapState:
    """Per-symbol mutable state for the RSI+VWAP strategy."""

    open_position_side: dict[str, str] = field(default_factory=dict)  # symbol -> "buy"/"sell"
    open_position_qty: dict[str, float] = field(default_factory=dict)


def _exit_long(
    now: datetime,
    symbol: str,
    last_close: float,
    indicators: dict[str, float],
    state: RsiVwapState,
) -> list[ProposedSignal]:
    """Emit an exit signal for an open long position."""
    qty = state.open_position_qty.pop(symbol)
    del state.open_position_side[symbol]
    return [
        ProposedSignal(
            timestamp=now,
            symbol=symbol,
            side="sell",
            qty=qty,
            signal_type="exit",
            price_at_signal=last_close,
            indicator_values=indicators,
        )
    ]


def _exit_short(
    now: datetime,
    symbol: str,
    last_close: float,
    indicators: dict[str, float],
    state: RsiVwapState,
) -> list[ProposedSignal]:
    """Emit an exit signal for an open short position."""
    qty = state.open_position_qty.pop(symbol)
    del state.open_position_side[symbol]
    return [
        ProposedSignal(
            timestamp=now,
            symbol=symbol,
            side="buy",
            qty=qty,
            signal_type="exit",
            price_at_signal=last_close,
            indicator_values=indicators,
        )
    ]


def _entry_long(  # noqa: PLR0913
    now: datetime,
    symbol: str,
    last_close: float,
    stop_distance: float,
    indicators: dict[str, float],
    cfg: RsiVwapConfig,
    state: RsiVwapState,
    equity: float,
) -> list[ProposedSignal]:
    """Emit an entry signal for a long position."""
    qty = round(cfg.risk_per_trade * equity / stop_distance)
    if qty <= 0:
        return []
    state.open_position_side[symbol] = "buy"
    state.open_position_qty[symbol] = float(qty)
    return [
        ProposedSignal(
            timestamp=now,
            symbol=symbol,
            side="buy",
            qty=float(qty),
            signal_type="entry",
            price_at_signal=last_close,
            stop_price=last_close - stop_distance,
            take_profit_price=None,
            indicator_values=indicators,
        )
    ]


def _entry_short(  # noqa: PLR0913
    now: datetime,
    symbol: str,
    last_close: float,
    stop_distance: float,
    indicators: dict[str, float],
    cfg: RsiVwapConfig,
    state: RsiVwapState,
    equity: float,
) -> list[ProposedSignal]:
    """Emit an entry signal for a short position."""
    qty = round(cfg.risk_per_trade * equity / stop_distance)
    if qty <= 0:
        return []
    state.open_position_side[symbol] = "sell"
    state.open_position_qty[symbol] = float(qty)
    return [
        ProposedSignal(
            timestamp=now,
            symbol=symbol,
            side="sell",
            qty=float(qty),
            signal_type="entry",
            price_at_signal=last_close,
            stop_price=last_close + stop_distance,
            take_profit_price=None,
            indicator_values=indicators,
        )
    ]


def compute_rsi_vwap_signals(  # noqa: PLR0913, PLR0911
    *,
    now: datetime,
    symbol: str,
    bars_today: Sequence[Bar],
    last_close: float,
    equity: float,
    cfg: RsiVwapConfig,
    state: RsiVwapState,
) -> list[ProposedSignal]:
    """Generate RSI+VWAP signals at the current tick."""
    if len(bars_today) < max(cfg.rsi_period + 1, cfg.atr_period + 1):
        return []

    highs = [b[0] for b in bars_today]
    lows = [b[1] for b in bars_today]
    closes = [b[3] for b in bars_today]
    volumes = [b[4] for b in bars_today]

    current_rsi = rsi(closes, period=cfg.rsi_period)
    current_vwap = vwap(highs, lows, closes, volumes)
    current_atr = atr(highs, lows, closes, period=cfg.atr_period)

    indicators: dict[str, float] = {
        "rsi": current_rsi,
        "vwap": current_vwap,
        "atr": current_atr,
    }
    open_side = state.open_position_side.get(symbol)

    if open_side == "buy" and current_rsi > _EXIT_RSI:
        return _exit_long(now, symbol, last_close, indicators, state)

    if open_side == "sell" and current_rsi < _EXIT_RSI:
        return _exit_short(now, symbol, last_close, indicators, state)

    if open_side is not None:
        return []  # already in a position; wait for exit

    stop_distance = cfg.atr_multiplier * current_atr
    if stop_distance <= 0.0:
        return []

    if current_rsi < cfg.rsi_long_threshold and last_close < current_vwap:
        return _entry_long(now, symbol, last_close, stop_distance, indicators, cfg, state, equity)

    if current_rsi > cfg.rsi_short_threshold and last_close > current_vwap:
        return _entry_short(now, symbol, last_close, stop_distance, indicators, cfg, state, equity)

    return []
