"""Base class for plutus strategies + the pure signal-recording layer.

`SignalRecorder` is the part that talks to the DB. It is intentionally separated
from the lumibot `Strategy` integration so that:
  - We can unit-test signal recording without lumibot.
  - Concrete strategies stay pure: they emit `ProposedSignal`s; the base class
    handles persistence and broker submission.

The lumibot integration (PlutusStrategy) is added in Task 10 (runner wiring),
since it requires lumibot Strategy machinery that's heavy to test in isolation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from sqlmodel import Session

from plutus.storage import Order, Signal

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from sqlalchemy.engine import Engine

Side = Literal["buy", "sell"]
SignalType = Literal["entry", "exit", "stop", "take_profit"]


@dataclass(frozen=True)
class ProposedSignal:
    """Pure-data representation of a strategy's proposed trade."""

    timestamp: datetime
    symbol: str
    side: Side
    qty: float
    signal_type: SignalType
    price_at_signal: float
    stop_price: float | None = None
    take_profit_price: float | None = None
    indicator_values: dict[str, float] = field(default_factory=dict)


@dataclass
class SignalRecorder:
    """Writes Signal + Order rows for a single strategy/run."""

    engine: Engine
    run_id: UUID
    strategy_name: str
    submit: bool

    def record(
        self,
        proposed: ProposedSignal,
        submit_fn: Callable[[ProposedSignal], str],
    ) -> None:
        """Persist a signal; submit to broker if enabled."""
        with Session(self.engine) as s:
            sig = Signal(
                run_id=self.run_id,
                strategy_name=self.strategy_name,
                timestamp=proposed.timestamp,
                symbol=proposed.symbol,
                side=proposed.side,
                qty=proposed.qty,
                signal_type=proposed.signal_type,
                price_at_signal=proposed.price_at_signal,
                stop_price=proposed.stop_price,
                take_profit_price=proposed.take_profit_price,
                indicator_values_json=json.dumps(proposed.indicator_values),
            )
            s.add(sig)
            s.commit()
            s.refresh(sig)

            if sig.id is None:  # pragma: no cover  # set by autoincrement after commit
                msg = "Signal.id is None after commit — autoincrement failed"
                raise RuntimeError(msg)
            if self.submit:
                alpaca_id = submit_fn(proposed)
                order = Order(
                    run_id=self.run_id,
                    signal_id=sig.id,
                    alpaca_order_id=alpaca_id,
                    status="submitted",
                    submitted_at=datetime.now(UTC),
                )
            else:
                order = Order(
                    run_id=self.run_id,
                    signal_id=sig.id,
                    alpaca_order_id=None,
                    status="skipped",
                    submitted_at=datetime.now(UTC),
                )
            s.add(order)
            s.commit()
