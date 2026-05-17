"""DB aggregations for `plutus report`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlmodel import Session, select

from plutus.storage import Order, Signal

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class StrategyRow:
    """Aggregated per-strategy metrics for a reporting window."""

    strategy: str
    signals: int
    filled: int
    avg_slip_bp: float | None


def build_summary(engine: Engine, *, since: datetime) -> list[StrategyRow]:
    """Aggregate signals + orders by strategy since `since`."""
    rows: dict[str, StrategyRow] = {}
    with Session(engine) as s:
        sigs = s.exec(select(Signal).where(Signal.timestamp >= since)).all()
        if not sigs:
            return []
        sig_ids = [sig.id for sig in sigs if sig.id is not None]
        ord_rows_all = s.exec(select(Order)).all()
        ord_rows = [o for o in ord_rows_all if o.signal_id in sig_ids]

    by_strat: dict[str, list[Signal]] = {}
    for sig in sigs:
        by_strat.setdefault(sig.strategy_name, []).append(sig)

    fills_by_sigid: dict[int, Order] = {
        o.signal_id: o for o in ord_rows if o.status == "filled" and o.filled_price is not None
    }

    for name, strat_sigs in by_strat.items():
        filled_count = 0
        slip_bps: list[float] = []
        for sig in strat_sigs:
            if sig.id is None:
                continue
            o = fills_by_sigid.get(sig.id)
            if o is None or o.filled_price is None:
                continue
            filled_count += 1
            if sig.price_at_signal > 0.0:
                slip = (o.filled_price - sig.price_at_signal) / sig.price_at_signal * 10_000.0
                slip_bps.append(slip)
        rows[name] = StrategyRow(
            strategy=name,
            signals=len(strat_sigs),
            filled=filled_count,
            avg_slip_bp=(sum(slip_bps) / len(slip_bps)) if slip_bps else None,
        )

    return sorted(rows.values(), key=lambda r: r.strategy)
