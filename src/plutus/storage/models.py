"""SQLModel tables for plutus.

Indexes:
  - signal_run_ts_idx on Signal(run_id, timestamp)
  - signal_strategy_ts_idx on Signal(strategy_name, timestamp)
  - daily_summary_unique on DailyRunSummary(strategy_name, trading_date)
"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

RunMode = Literal["paper", "backtest"]
Side = Literal["buy", "sell"]
SignalType = Literal["entry", "exit", "stop", "take_profit"]


class Run(SQLModel, table=True):
    """One invocation of one strategy, paper or backtest."""

    id: UUID = Field(primary_key=True)
    strategy_name: str = Field(index=True)
    mode: str
    started_at: datetime
    ended_at: datetime | None = None
    config_json: str


class Signal(SQLModel, table=True):
    """A proposed trade emitted by a strategy."""

    __table_args__ = (  # type: ignore[assignment]
        {"sqlite_autoincrement": True},
    )

    id: int | None = Field(default=None, primary_key=True)
    run_id: UUID = Field(foreign_key="run.id", index=True)
    strategy_name: str = Field(index=True)
    timestamp: datetime = Field(index=True)
    symbol: str
    side: str
    qty: float
    signal_type: str
    price_at_signal: float
    stop_price: float | None = None
    take_profit_price: float | None = None
    indicator_values_json: str


class Order(SQLModel, table=True):
    """Either a broker-submitted order or a skipped (DB-only) record."""

    __table_args__ = (  # type: ignore[assignment]
        {"sqlite_autoincrement": True},
    )

    id: int | None = Field(default=None, primary_key=True)
    run_id: UUID = Field(foreign_key="run.id", index=True)
    signal_id: int = Field(foreign_key="signal.id", index=True)
    alpaca_order_id: str | None = None
    status: str
    filled_price: float | None = None
    filled_qty: float | None = None
    submitted_at: datetime
    filled_at: datetime | None = None


class DailyRunSummary(SQLModel, table=True):
    """One row per (strategy, trading_date) for fast reporting."""

    __table_args__ = (
        UniqueConstraint("strategy_name", "trading_date", name="daily_summary_unique"),
        {"sqlite_autoincrement": True},
    )

    id: int | None = Field(default=None, primary_key=True)
    run_id: UUID = Field(foreign_key="run.id")
    strategy_name: str = Field(index=True)
    trading_date: date
    signals_count: int
    orders_filled_count: int
    realized_pnl: float
    open_positions_count: int
