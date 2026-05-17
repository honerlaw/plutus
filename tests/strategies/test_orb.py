"""Tests for the Opening Range Breakout pure signal layer."""

from __future__ import annotations

from datetime import UTC, datetime

from plutus.strategies.orb import OrbConfig, OrbState, compute_orb_signals


def _ts(hour: int, minute: int) -> datetime:
    return datetime(2026, 5, 18, hour, minute, tzinfo=UTC)


def test_no_signal_before_or_window_closes() -> None:
    cfg = OrbConfig(opening_range_minutes=15, risk_per_trade=0.005)
    state = OrbState()
    sigs = compute_orb_signals(
        now=_ts(13, 35),  # 9:35 ET == 13:35 UTC
        symbol="AAPL",
        last_close=200.0,
        bars_today=[(200.0, 201.0, 199.0, 200.5, 1000.0)] * 5,
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    assert sigs == []


def test_long_entry_on_breakout_above_or_high() -> None:
    cfg = OrbConfig(opening_range_minutes=15, risk_per_trade=0.005)
    state = OrbState()
    # Pre-fill the OR window via a 9:45 tick first
    compute_orb_signals(
        now=_ts(13, 45),
        symbol="AAPL",
        last_close=200.0,
        bars_today=[(201.0, 200.0, 199.0, 199.5, 1000.0)] * 15,  # OR: high=201, low=199
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    # Now price breaks above OR-high
    sigs = compute_orb_signals(
        now=_ts(14, 0),
        symbol="AAPL",
        last_close=202.0,
        bars_today=[(201.0, 200.0, 199.0, 199.5, 1000.0)] * 15
        + [(202.5, 202.0, 201.5, 202.0, 500.0)],
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    assert len(sigs) == 1
    s = sigs[0]
    assert s.side == "buy"
    assert s.symbol == "AAPL"
    assert s.signal_type == "entry"
    # stop at OR-low (199), tp = entry + (OR-high - OR-low) = 202 + 2 = 204
    assert s.stop_price == 199.0
    assert s.take_profit_price == 204.0
    # qty = 0.005 * 100000 / (202 - 199) = 500/3 ~= 166.67, rounded
    assert s.qty == round(500.0 / 3.0)


def test_short_entry_on_breakdown_below_or_low() -> None:
    cfg = OrbConfig(opening_range_minutes=15, risk_per_trade=0.005)
    state = OrbState()
    compute_orb_signals(
        now=_ts(13, 45),
        symbol="AAPL",
        last_close=200.0,
        bars_today=[(201.0, 200.0, 199.0, 199.5, 1000.0)] * 15,
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    sigs = compute_orb_signals(
        now=_ts(14, 0),
        symbol="AAPL",
        last_close=198.0,
        bars_today=[(201.0, 200.0, 199.0, 199.5, 1000.0)] * 15
        + [(199.0, 198.5, 197.5, 198.0, 500.0)],
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    assert len(sigs) == 1
    assert sigs[0].side == "sell"
    assert sigs[0].stop_price == 201.0


def test_only_one_entry_per_symbol_per_day() -> None:
    cfg = OrbConfig(opening_range_minutes=15, risk_per_trade=0.005)
    state = OrbState()
    compute_orb_signals(
        now=_ts(13, 45),
        symbol="AAPL",
        last_close=200.0,
        bars_today=[(201.0, 200.0, 199.0, 199.5, 1000.0)] * 15,
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    compute_orb_signals(
        now=_ts(14, 0),
        symbol="AAPL",
        last_close=202.0,
        bars_today=[(201.0, 200.0, 199.0, 199.5, 1000.0)] * 15
        + [(202.5, 202.0, 201.5, 202.0, 500.0)],
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    # second breakout same day -> no new entry
    sigs = compute_orb_signals(
        now=_ts(14, 15),
        symbol="AAPL",
        last_close=203.0,
        bars_today=[(201.0, 200.0, 199.0, 199.5, 1000.0)] * 15
        + [(203.5, 203.0, 202.5, 203.0, 500.0)],
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    assert sigs == []


def test_eod_exit_signal_at_1555() -> None:
    cfg = OrbConfig(opening_range_minutes=15, risk_per_trade=0.005)
    state = OrbState()
    compute_orb_signals(
        now=_ts(13, 45),
        symbol="AAPL",
        last_close=200.0,
        bars_today=[(201.0, 200.0, 199.0, 199.5, 1000.0)] * 15,
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    compute_orb_signals(
        now=_ts(14, 0),
        symbol="AAPL",
        last_close=202.0,
        bars_today=[(201.0, 200.0, 199.0, 199.5, 1000.0)] * 15
        + [(202.5, 202.0, 201.5, 202.0, 500.0)],
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    sigs = compute_orb_signals(
        now=_ts(19, 55),  # 15:55 ET == 19:55 UTC
        symbol="AAPL",
        last_close=201.0,
        bars_today=[(201.0, 200.0, 199.0, 199.5, 1000.0)] * 15
        + [(202.5, 202.0, 201.5, 202.0, 500.0)] * 100,
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    assert any(s.signal_type == "exit" for s in sigs)
