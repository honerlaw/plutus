"""Donchian channel swing breakout strategy — pure signal logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from plutus.strategies.base import ProposedSignal
from plutus.strategies.indicators import atr, donchian
from plutus.strategies.registry import register

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

Bar = tuple[float, float, float, float, float]


@dataclass(frozen=True)
class DonchianConfig:
    """Configuration for the Donchian channel swing breakout strategy."""

    channel_period: int = 20
    atr_period: int = 14
    atr_multiplier: float = 2.0
    max_hold_bars: int = 35
    risk_per_trade: float = 0.005


@dataclass
class DonchianState:
    """Per-symbol mutable state for the Donchian swing strategy."""

    open_side: dict[str, str] = field(default_factory=dict)  # symbol -> "buy"/"sell"
    open_qty: dict[str, float] = field(default_factory=dict)
    entry_bar_index: dict[str, int] = field(default_factory=dict)
    trailing_stop: dict[str, float] = field(default_factory=dict)
    bar_count: dict[str, int] = field(default_factory=dict)


@register("donchian_swing")
class _DonchianMarker:
    """Registration marker; runner replaces with lumibot adapter (Task 14)."""

    def __init__(self, **kwargs: float) -> None:
        self.cfg = DonchianConfig(
            channel_period=int(kwargs.get("channel_period", 20)),
            atr_period=int(kwargs.get("atr_period", 14)),
            atr_multiplier=float(kwargs.get("atr_multiplier", 2.0)),
            max_hold_bars=int(kwargs.get("max_hold_bars", 35)),
            risk_per_trade=float(kwargs.get("risk_per_trade", 0.005)),
        )


def _close_position(
    symbol: str,
    state: DonchianState,
) -> float:
    """Remove the open position from state and return the qty."""
    qty = state.open_qty.pop(symbol)
    del state.open_side[symbol]
    del state.trailing_stop[symbol]
    del state.entry_bar_index[symbol]
    return qty


def _update_trailing_stop(
    symbol: str,
    open_side: str,
    last_close: float,
    stop_distance: float,
    state: DonchianState,
) -> None:
    """Advance trailing stop in the favorable direction."""
    if open_side == "buy":
        new_stop = last_close - stop_distance
        state.trailing_stop[symbol] = max(state.trailing_stop[symbol], new_stop)
    else:
        new_stop = last_close + stop_distance
        state.trailing_stop[symbol] = min(state.trailing_stop[symbol], new_stop)


def _check_stop_hit(  # noqa: PLR0913
    now: datetime,
    symbol: str,
    open_side: str,
    last_close: float,
    indicators: dict[str, float],
    state: DonchianState,
) -> list[ProposedSignal] | None:
    """Return a stop signal if the trailing stop was breached, else None."""
    stop = state.trailing_stop[symbol]
    if open_side == "buy" and last_close <= stop:
        qty = _close_position(symbol, state)
        return [
            ProposedSignal(
                timestamp=now,
                symbol=symbol,
                side="sell",
                qty=qty,
                signal_type="stop",
                price_at_signal=last_close,
                indicator_values=indicators,
            )
        ]
    if open_side == "sell" and last_close >= stop:
        qty = _close_position(symbol, state)
        return [
            ProposedSignal(
                timestamp=now,
                symbol=symbol,
                side="buy",
                qty=qty,
                signal_type="stop",
                price_at_signal=last_close,
                indicator_values=indicators,
            )
        ]
    return None


def _check_max_hold(  # noqa: PLR0913
    now: datetime,
    symbol: str,
    open_side: str,
    last_close: float,
    held: int,
    indicators: dict[str, float],
    cfg: DonchianConfig,
    state: DonchianState,
) -> list[ProposedSignal] | None:
    """Return an exit signal if max hold bars exceeded, else None."""
    if held <= cfg.max_hold_bars:
        return None
    qty = _close_position(symbol, state)
    opposite = "sell" if open_side == "buy" else "buy"
    return [
        ProposedSignal(
            timestamp=now,
            symbol=symbol,
            side=opposite,
            qty=qty,
            signal_type="exit",
            price_at_signal=last_close,
            indicator_values={**indicators, "reason_max_hold": 1.0},
        )
    ]


def _manage_open_position(  # noqa: PLR0913
    now: datetime,
    symbol: str,
    last_close: float,
    stop_distance: float,
    indicators: dict[str, float],
    cfg: DonchianConfig,
    state: DonchianState,
) -> list[ProposedSignal]:
    """Update trailing stop and check for exit conditions on an open position."""
    open_side = state.open_side[symbol]
    held = state.bar_count[symbol] - state.entry_bar_index[symbol]

    _update_trailing_stop(symbol, open_side, last_close, stop_distance, state)

    stop_signal = _check_stop_hit(now, symbol, open_side, last_close, indicators, state)
    if stop_signal is not None:
        return stop_signal

    max_hold_signal = _check_max_hold(
        now,
        symbol,
        open_side,
        last_close,
        held,
        indicators,
        cfg,
        state,
    )
    if max_hold_signal is not None:
        return max_hold_signal

    return []


def _try_entry(  # noqa: PLR0913
    now: datetime,
    symbol: str,
    last_close: float,
    prior_hi: float,
    prior_lo: float,
    stop_distance: float,
    equity: float,
    indicators: dict[str, float],
    cfg: DonchianConfig,
    state: DonchianState,
) -> list[ProposedSignal]:
    """Attempt to open a new position based on Donchian breakout."""
    if stop_distance <= 0.0:
        return []

    if last_close > prior_hi:
        return _open_long(now, symbol, last_close, stop_distance, equity, indicators, cfg, state)

    if last_close < prior_lo:
        return _open_short(now, symbol, last_close, stop_distance, equity, indicators, cfg, state)

    return []


def _open_long(  # noqa: PLR0913
    now: datetime,
    symbol: str,
    last_close: float,
    stop_distance: float,
    equity: float,
    indicators: dict[str, float],
    cfg: DonchianConfig,
    state: DonchianState,
) -> list[ProposedSignal]:
    """Open a long position."""
    qty = round(cfg.risk_per_trade * equity / stop_distance)
    if qty <= 0:
        return []
    stop_price = last_close - stop_distance
    state.open_side[symbol] = "buy"
    state.open_qty[symbol] = float(qty)
    state.trailing_stop[symbol] = stop_price
    state.entry_bar_index[symbol] = state.bar_count[symbol]
    return [
        ProposedSignal(
            timestamp=now,
            symbol=symbol,
            side="buy",
            qty=float(qty),
            signal_type="entry",
            price_at_signal=last_close,
            stop_price=stop_price,
            take_profit_price=None,
            indicator_values=indicators,
        )
    ]


def _open_short(  # noqa: PLR0913
    now: datetime,
    symbol: str,
    last_close: float,
    stop_distance: float,
    equity: float,
    indicators: dict[str, float],
    cfg: DonchianConfig,
    state: DonchianState,
) -> list[ProposedSignal]:
    """Open a short position."""
    qty = round(cfg.risk_per_trade * equity / stop_distance)
    if qty <= 0:
        return []
    stop_price = last_close + stop_distance
    state.open_side[symbol] = "sell"
    state.open_qty[symbol] = float(qty)
    state.trailing_stop[symbol] = stop_price
    state.entry_bar_index[symbol] = state.bar_count[symbol]
    return [
        ProposedSignal(
            timestamp=now,
            symbol=symbol,
            side="sell",
            qty=float(qty),
            signal_type="entry",
            price_at_signal=last_close,
            stop_price=stop_price,
            take_profit_price=None,
            indicator_values=indicators,
        )
    ]


def compute_donchian_signals(  # noqa: PLR0913
    *,
    now: datetime,
    symbol: str,
    bars: Sequence[Bar],
    last_close: float,
    equity: float,
    cfg: DonchianConfig,
    state: DonchianState,
) -> list[ProposedSignal]:
    """Generate Donchian swing signals at the current bar."""
    needed = max(cfg.channel_period + 1, cfg.atr_period + 1)
    if len(bars) < needed:
        return []

    highs = [b[0] for b in bars]
    lows = [b[1] for b in bars]
    closes = [b[3] for b in bars]

    # Donchian computed on bars *prior* to the current one to avoid look-ahead
    prior_hi, prior_lo = donchian(highs[:-1], lows[:-1], cfg.channel_period)
    current_atr = atr(highs, lows, closes, period=cfg.atr_period)
    stop_distance = cfg.atr_multiplier * current_atr

    state.bar_count[symbol] = state.bar_count.get(symbol, 0) + 1

    indicators: dict[str, float] = {
        "donchian_high": prior_hi,
        "donchian_low": prior_lo,
        "atr": current_atr,
    }

    if state.open_side.get(symbol) is not None:
        return _manage_open_position(
            now,
            symbol,
            last_close,
            stop_distance,
            indicators,
            cfg,
            state,
        )

    return _try_entry(
        now,
        symbol,
        last_close,
        prior_hi,
        prior_lo,
        stop_distance,
        equity,
        indicators,
        cfg,
        state,
    )
