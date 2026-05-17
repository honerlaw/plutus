"""Tests for the Donchian swing strategy pure signal layer."""

from __future__ import annotations

from datetime import UTC, datetime

from plutus.strategies.donchian_swing import (
    DonchianConfig,
    DonchianState,
    compute_donchian_signals,
)


def _ts() -> datetime:
    return datetime(2026, 5, 18, 14, 0, tzinfo=UTC)


def _flat(n: int, level: float = 100.0) -> list[tuple[float, float, float, float, float]]:
    return [(level + 0.5, level - 0.5, level, level, 1000.0)] * n


def test_long_entry_when_close_breaks_above_prior_donchian_high() -> None:
    cfg = DonchianConfig(
        channel_period=20,
        atr_period=14,
        atr_multiplier=2.0,
        max_hold_bars=35,
        risk_per_trade=0.005,
    )
    state = DonchianState()
    bars = _flat(30, 100.0)  # 30 quiet bars
    bars.append((105.0, 100.5, 100.0, 104.5, 2000.0))  # breakout bar

    sigs = compute_donchian_signals(
        now=_ts(),
        symbol="AAPL",
        bars=bars,
        last_close=104.5,
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    assert len(sigs) == 1
    assert sigs[0].side == "buy"
    assert sigs[0].signal_type == "entry"


def test_short_entry_when_close_breaks_below_prior_donchian_low() -> None:
    cfg = DonchianConfig(
        channel_period=20,
        atr_period=14,
        atr_multiplier=2.0,
        max_hold_bars=35,
        risk_per_trade=0.005,
    )
    state = DonchianState()
    bars = _flat(30, 100.0)
    bars.append((100.0, 95.0, 100.0, 95.5, 2000.0))

    sigs = compute_donchian_signals(
        now=_ts(),
        symbol="AAPL",
        bars=bars,
        last_close=95.5,
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    assert len(sigs) == 1
    assert sigs[0].side == "sell"


def test_trailing_stop_tightens_on_favorable_move() -> None:
    cfg = DonchianConfig(
        channel_period=20,
        atr_period=14,
        atr_multiplier=2.0,
        max_hold_bars=35,
        risk_per_trade=0.005,
    )
    state = DonchianState()
    bars = _flat(30, 100.0)
    bars.append((105.0, 100.5, 100.0, 104.5, 2000.0))

    compute_donchian_signals(
        now=_ts(),
        symbol="AAPL",
        bars=bars,
        last_close=104.5,
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    initial_stop = state.trailing_stop["AAPL"]

    bars.append((110.0, 106.0, 105.0, 109.5, 2000.0))
    compute_donchian_signals(
        now=_ts(),
        symbol="AAPL",
        bars=bars,
        last_close=109.5,
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    assert state.trailing_stop["AAPL"] > initial_stop


def test_exit_when_stop_hit() -> None:
    cfg = DonchianConfig(
        channel_period=20,
        atr_period=14,
        atr_multiplier=2.0,
        max_hold_bars=35,
        risk_per_trade=0.005,
    )
    state = DonchianState()
    bars = _flat(30, 100.0)
    bars.append((105.0, 100.5, 100.0, 104.5, 2000.0))
    compute_donchian_signals(
        now=_ts(),
        symbol="AAPL",
        bars=bars,
        last_close=104.5,
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    stop = state.trailing_stop["AAPL"]

    bars.append((104.0, stop - 1.0, 104.0, stop - 0.5, 2000.0))
    sigs = compute_donchian_signals(
        now=_ts(),
        symbol="AAPL",
        bars=bars,
        last_close=stop - 0.5,
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    assert any(s.signal_type == "stop" for s in sigs)


def test_exit_after_max_hold_bars() -> None:
    cfg = DonchianConfig(
        channel_period=20,
        atr_period=14,
        atr_multiplier=2.0,
        max_hold_bars=3,
        risk_per_trade=0.005,
    )
    state = DonchianState()
    bars = _flat(30, 100.0)
    bars.append((105.0, 100.5, 100.0, 104.5, 2000.0))
    compute_donchian_signals(
        now=_ts(),
        symbol="AAPL",
        bars=bars,
        last_close=104.5,
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    # advance 3 more bars within trailing stop
    for _ in range(3):
        bars.append((104.5, 104.0, 104.0, 104.2, 1000.0))
        compute_donchian_signals(
            now=_ts(),
            symbol="AAPL",
            bars=bars,
            last_close=104.2,
            equity=100_000.0,
            cfg=cfg,
            state=state,
        )
    bars.append((104.5, 104.0, 104.0, 104.2, 1000.0))
    sigs = compute_donchian_signals(
        now=_ts(),
        symbol="AAPL",
        bars=bars,
        last_close=104.2,
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    assert any(s.signal_type == "exit" for s in sigs)
