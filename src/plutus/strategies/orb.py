"""Opening Range Breakout strategy -- pure signal logic.

Operates on UTC timestamps. The US equity session in UTC (during DST) is
13:30-20:00 (9:30-16:00 ET). When DST is not in effect, the session is
14:30-21:00 UTC. The lumibot adapter is responsible for passing
DST-correct timestamps in `now`; this module only checks elapsed minutes
from market open as supplied via OrbState.session_open_utc.

For test simplicity we treat `now` as already-correct UTC and infer the
session open from the date -- if state.session_open_utc is None on the
first call of a day, we set it to today at 13:30 UTC (DST default).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING

from plutus.strategies.base import ProposedSignal
from plutus.strategies.registry import register

if TYPE_CHECKING:
    from collections.abc import Sequence

# Bar tuple: (open, high, low, close, volume) -- standard OHLCV ordering.
Bar = tuple[float, float, float, float, float]


@dataclass(frozen=True)
class OrbConfig:
    """Configuration for the Opening Range Breakout strategy."""

    opening_range_minutes: int = 15
    risk_per_trade: float = 0.005


@dataclass
class OrbState:
    """Per-symbol state. Reset daily inside compute_orb_signals."""

    session_date: date | None = None
    session_open_utc: datetime | None = None
    or_high: float | None = None
    or_low: float | None = None
    entered_today: dict[str, bool] = field(default_factory=dict)
    open_position: dict[str, ProposedSignal] = field(default_factory=dict)


def _reset_if_new_day(now: datetime, state: OrbState) -> None:
    if state.session_date == now.date():
        return
    state.session_date = now.date()
    state.session_open_utc = datetime.combine(now.date(), time(13, 30), tzinfo=UTC)
    state.or_high = None
    state.or_low = None
    state.entered_today = {}
    state.open_position = {}


def _seal_or_window(bars_today: Sequence[Bar], cfg: OrbConfig, state: OrbState) -> None:
    if state.or_high is not None:
        return
    window = bars_today[: cfg.opening_range_minutes]
    if len(window) < cfg.opening_range_minutes:
        return
    state.or_high = max(max(b[0], b[1], b[2], b[3]) for b in window)
    state.or_low = min(min(b[0], b[1], b[2], b[3]) for b in window)


def _emit_eod_exit(
    now: datetime,
    symbol: str,
    last_close: float,
    state: OrbState,
) -> list[ProposedSignal]:
    """Emit an EOD exit signal if we hold an open position for the symbol."""
    if symbol not in state.open_position:
        return []
    open_sig = state.open_position.pop(symbol)
    return [
        ProposedSignal(
            timestamp=now,
            symbol=symbol,
            side="sell" if open_sig.side == "buy" else "buy",
            qty=open_sig.qty,
            signal_type="exit",
            price_at_signal=last_close,
            indicator_values={"reason_eod": 1.0},
        )
    ]


def _emit_long_entry(  # noqa: PLR0913
    now: datetime,
    symbol: str,
    last_close: float,
    or_high: float,
    or_low: float,
    or_width: float,
    equity: float,
    cfg: OrbConfig,
    state: OrbState,
) -> list[ProposedSignal]:
    """Emit a long entry signal on breakout above OR high."""
    risk_per_share = last_close - or_low
    qty = round(cfg.risk_per_trade * equity / risk_per_share)
    if qty <= 0:
        return []
    sig = ProposedSignal(
        timestamp=now,
        symbol=symbol,
        side="buy",
        qty=float(qty),
        signal_type="entry",
        price_at_signal=last_close,
        stop_price=or_low,
        take_profit_price=last_close + or_width,
        indicator_values={"or_high": or_high, "or_low": or_low},
    )
    state.entered_today[symbol] = True
    state.open_position[symbol] = sig
    return [sig]


def _emit_short_entry(  # noqa: PLR0913
    now: datetime,
    symbol: str,
    last_close: float,
    or_high: float,
    or_low: float,
    or_width: float,
    equity: float,
    cfg: OrbConfig,
    state: OrbState,
) -> list[ProposedSignal]:
    """Emit a short entry signal on breakdown below OR low."""
    risk_per_share = or_high - last_close
    qty = round(cfg.risk_per_trade * equity / risk_per_share)
    if qty <= 0:
        return []
    sig = ProposedSignal(
        timestamp=now,
        symbol=symbol,
        side="sell",
        qty=float(qty),
        signal_type="entry",
        price_at_signal=last_close,
        stop_price=or_high,
        take_profit_price=last_close - or_width,
        indicator_values={"or_high": or_high, "or_low": or_low},
    )
    state.entered_today[symbol] = True
    state.open_position[symbol] = sig
    return [sig]


@register("orb")
class _OrbRegistrationMarker:
    """Placeholder so the registry knows ORB exists.

    The lumibot adapter (Task 14) will replace this with a real Strategy
    subclass that calls compute_orb_signals.
    """

    def __init__(self, **kwargs: float) -> None:
        self.cfg = OrbConfig(
            opening_range_minutes=int(kwargs.get("opening_range_minutes", 15)),
            risk_per_trade=float(kwargs.get("risk_per_trade", 0.005)),
        )


def compute_orb_signals(  # noqa: PLR0913, PLR0911
    *,
    now: datetime,
    symbol: str,
    last_close: float,
    bars_today: Sequence[Bar],
    equity: float,
    cfg: OrbConfig,
    state: OrbState,
) -> list[ProposedSignal]:
    """Pure signal generator for a single symbol at a single tick."""
    _reset_if_new_day(now, state)
    if state.session_open_utc is None:  # pragma: no cover
        msg = "session_open_utc is None after _reset_if_new_day -- invariant violated"
        raise RuntimeError(msg)

    minutes_elapsed = (now - state.session_open_utc).total_seconds() / 60.0
    if minutes_elapsed < cfg.opening_range_minutes:
        return []

    _seal_or_window(bars_today, cfg, state)
    if state.or_high is None or state.or_low is None:
        return []

    # End-of-day exit at 15:55 ET (19:55 UTC during DST)
    eod = state.session_open_utc + timedelta(hours=6, minutes=25)
    if now >= eod:
        return _emit_eod_exit(now, symbol, last_close, state)

    if state.entered_today.get(symbol, False):
        return []

    or_high = state.or_high
    or_low = state.or_low
    or_width = or_high - or_low
    if or_width <= 0.0:
        return []

    if last_close > or_high:
        return _emit_long_entry(
            now, symbol, last_close, or_high, or_low, or_width, equity, cfg, state
        )
    if last_close < or_low:
        return _emit_short_entry(
            now, symbol, last_close, or_high, or_low, or_width, equity, cfg, state
        )

    return []
