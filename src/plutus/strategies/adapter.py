"""Lumibot Strategy adapters that drive the pure compute_*_signals layers.

Each adapter class:
  - Is registered in the strategy registry so it can be looked up by name.
  - Can be instantiated standalone (no lumibot broker required) for testing.
  - Exposes ``attach_engine`` to wire up the DB before the trading loop starts.
  - Exposes ``to_lumibot_strategy(broker)`` to produce a live lumibot Strategy
    instance when the runner is ready to start.

``lumibot.strategies`` is imported at module level because conftest.py
pre-warms the module cache before pytest's -W error filter activates.

The on_trading_iteration / _submit_to_broker methods on the inner Strategy
subclasses are not covered by unit tests because they require a live broker
data-source; they are exercised by ``plutus run``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, ClassVar

from lumibot.entities import Order
from lumibot.strategies import Strategy

from plutus.strategies.base import ProposedSignal, SignalRecorder
from plutus.strategies.donchian_swing import (
    DonchianConfig,
    DonchianState,
    compute_donchian_signals,
)
from plutus.strategies.orb import OrbConfig, OrbState, compute_orb_signals
from plutus.strategies.registry import register
from plutus.strategies.rsi_vwap import (
    RsiVwapConfig,
    RsiVwapState,
    compute_rsi_vwap_signals,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.engine import Engine


class _PlutusAdapter:
    """Common DB-recording plumbing shared by every plutus adapter.

    Deliberately does NOT inherit lumibot.Strategy so that adapters can be
    instantiated in tests without a live broker.  The runner wires a real
    lumibot Strategy at startup via ``to_lumibot_strategy(broker)``.
    """

    _registry_name: ClassVar[str] = ""  # overridden in each subclass

    def __init__(self, **kwargs: Any) -> None:
        """Initialise adapter with optional config keyword arguments."""
        self._kwargs = kwargs
        self._engine: Engine | None = None
        self._run_id: UUID | None = None
        self._submit: bool = False
        self._recorder: SignalRecorder | None = None

    def attach_engine(self, *, engine: Engine, run_id: UUID, submit: bool) -> None:
        """Wire the DB engine + run before lumibot starts the loop."""
        self._engine = engine
        self._run_id = run_id
        self._submit = submit
        self._recorder = SignalRecorder(
            engine=engine,
            run_id=run_id,
            strategy_name=self._registry_name,
            submit=submit,
        )

    def _record_signal(
        self,
        sig: ProposedSignal,
        submit_fn: Any,
    ) -> None:
        if self._recorder is None:
            msg = "attach_engine() must be called before _record_signal()"
            raise RuntimeError(msg)
        self._recorder.record(sig, submit_fn=submit_fn)

    def to_lumibot_strategy(self, broker: Any) -> Any:
        """Return a live lumibot Strategy connected to *broker*.

        The returned object drives ``on_trading_iteration`` via this adapter's
        config/state.  Called by the runner just before ``Trader.run()``.
        """
        raise NotImplementedError  # pragma: no cover


def _submit_order(sig: ProposedSignal, lumibot_strategy: Strategy) -> str:  # pragma: no cover
    """Submit *sig* as a market order via *lumibot_strategy* and return the id."""
    order = lumibot_strategy.create_order(
        sig.symbol,
        Decimal(str(sig.qty)),
        sig.side,
        order_type=Order.OrderType.MARKET,
    )
    lumibot_strategy.submit_order(order)
    return str(getattr(order, "identifier", ""))


@register("orb")
class OrbStrategy(_PlutusAdapter):
    """Lumibot adapter for Opening Range Breakout."""

    _registry_name: ClassVar[str] = "orb"

    def __init__(self, **kwargs: Any) -> None:
        """Initialise OrbStrategy with optional config overrides."""
        super().__init__(**kwargs)
        self._cfg = OrbConfig(
            opening_range_minutes=int(kwargs.get("opening_range_minutes", 15)),
            risk_per_trade=float(kwargs.get("risk_per_trade", 0.005)),
        )
        self._state: dict[str, OrbState] = {}

    def to_lumibot_strategy(self, broker: Any) -> Any:  # pragma: no cover
        """Build a live lumibot Strategy that calls compute_orb_signals."""
        cfg = self._cfg
        state = self._state
        record = self._record_signal

        class _OrbLumibot(Strategy):
            def on_trading_iteration(self) -> None:
                now = datetime.now(UTC)
                equity = float(self.get_portfolio_value())
                for symbol in self.universe:  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
                    bars: list[tuple[float, float, float, float, float]] = []
                    price = self.get_last_price(symbol)
                    last_close = float(price) if price is not None else 0.0
                    sym_state = state.setdefault(symbol, OrbState())
                    sigs = compute_orb_signals(
                        now=now,
                        symbol=symbol,
                        last_close=last_close,
                        bars_today=bars,
                        equity=equity,
                        cfg=cfg,
                        state=sym_state,
                    )
                    lbot = self
                    for s in sigs:
                        record(s, submit_fn=lambda sig, lb=lbot: _submit_order(sig, lb))

        return _OrbLumibot(broker=broker, name="orb")


@register("rsi_vwap")
class RsiVwapStrategy(_PlutusAdapter):
    """Lumibot adapter for RSI+VWAP mean reversion."""

    _registry_name: ClassVar[str] = "rsi_vwap"

    def __init__(self, **kwargs: Any) -> None:
        """Initialise RsiVwapStrategy with optional config overrides."""
        super().__init__(**kwargs)
        self._cfg = RsiVwapConfig(
            rsi_period=int(kwargs.get("rsi_period", 14)),
            rsi_long_threshold=float(kwargs.get("rsi_long_threshold", 30.0)),
            rsi_short_threshold=float(kwargs.get("rsi_short_threshold", 70.0)),
            atr_period=int(kwargs.get("atr_period", 14)),
            atr_multiplier=float(kwargs.get("atr_multiplier", 1.5)),
            risk_per_trade=float(kwargs.get("risk_per_trade", 0.005)),
        )
        self._state = RsiVwapState()

    def to_lumibot_strategy(self, broker: Any) -> Any:  # pragma: no cover
        """Build a live lumibot Strategy that calls compute_rsi_vwap_signals."""
        cfg = self._cfg
        state = self._state
        record = self._record_signal

        class _RsiVwapLumibot(Strategy):
            def on_trading_iteration(self) -> None:
                now = datetime.now(UTC)
                equity = float(self.get_portfolio_value())
                for symbol in self.universe:  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
                    bars: list[tuple[float, float, float, float, float]] = []
                    price = self.get_last_price(symbol)
                    last_close = float(price) if price is not None else 0.0
                    sigs = compute_rsi_vwap_signals(
                        now=now,
                        symbol=symbol,
                        bars_today=bars,
                        last_close=last_close,
                        equity=equity,
                        cfg=cfg,
                        state=state,
                    )
                    lbot = self
                    for s in sigs:
                        record(s, submit_fn=lambda sig, lb=lbot: _submit_order(sig, lb))

        return _RsiVwapLumibot(broker=broker, name="rsi_vwap")


@register("donchian_swing")
class DonchianSwingStrategy(_PlutusAdapter):
    """Lumibot adapter for Donchian swing breakout."""

    _registry_name: ClassVar[str] = "donchian_swing"

    def __init__(self, **kwargs: Any) -> None:
        """Initialise DonchianSwingStrategy with optional config overrides."""
        super().__init__(**kwargs)
        self._cfg = DonchianConfig(
            channel_period=int(kwargs.get("channel_period", 20)),
            atr_period=int(kwargs.get("atr_period", 14)),
            atr_multiplier=float(kwargs.get("atr_multiplier", 2.0)),
            max_hold_bars=int(kwargs.get("max_hold_bars", 35)),
            risk_per_trade=float(kwargs.get("risk_per_trade", 0.005)),
        )
        self._state = DonchianState()

    def to_lumibot_strategy(self, broker: Any) -> Any:  # pragma: no cover
        """Build a live lumibot Strategy that calls compute_donchian_signals."""
        cfg = self._cfg
        state = self._state
        record = self._record_signal

        class _DonchianLumibot(Strategy):
            def on_trading_iteration(self) -> None:
                now = datetime.now(UTC)
                equity = float(self.get_portfolio_value())
                for symbol in self.universe:  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
                    bars: list[tuple[float, float, float, float, float]] = []
                    price = self.get_last_price(symbol)
                    last_close = float(price) if price is not None else 0.0
                    sigs = compute_donchian_signals(
                        now=now,
                        symbol=symbol,
                        bars=bars,
                        last_close=last_close,
                        equity=equity,
                        cfg=cfg,
                        state=state,
                    )
                    lbot = self
                    for s in sigs:
                        record(s, submit_fn=lambda sig, lb=lbot: _submit_order(sig, lb))

        return _DonchianLumibot(broker=broker, name="donchian_swing")
