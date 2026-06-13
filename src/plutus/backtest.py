"""Run a single strategy in backtest mode against Alpaca historical bars."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, time
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from lumibot.backtesting import AlpacaBacktesting
from sqlmodel import Session

import plutus.strategies  # noqa: F401 -- registers all strategies
from plutus.config import Settings
from plutus.logging import configure_logging
from plutus.storage import Run, init_db
from plutus.strategies.registry import REGISTRY
from plutus.universe import load_universe

if TYPE_CHECKING:
    from pathlib import Path


def _run_alpaca_backtest(
    strategy_cls: type[Any],
    start: datetime,
    end: datetime,
    kwargs: dict[str, object],
) -> None:
    """Thin wrapper around lumibot's AlpacaBacktesting.run_backtest for patchability."""
    strategy_cls.run_backtest(
        AlpacaBacktesting,
        start,
        end,
        parameters=kwargs,
    )


def run_backtest(
    *,
    strategy_name: str,
    start: date,
    end: date,
    universe_path: Path,
) -> None:
    """Execute one strategy backtest. Records its own Run row with mode=backtest."""
    settings = Settings()
    configure_logging(settings.log_level)
    engine = init_db(settings.database_url)

    try:
        universe = load_universe(universe_path)
        if strategy_name not in REGISTRY:
            msg = f"unknown strategy {strategy_name}; registered: {sorted(REGISTRY)}"
            raise KeyError(msg)
        if strategy_name not in universe.get("strategies", {}):
            msg = f"{strategy_name} not present in universe config {universe_path}"
            raise KeyError(msg)

        params = {k: v for k, v in universe["strategies"][strategy_name].items() if k != "enabled"}
        run_id = uuid4()
        with Session(engine) as s:
            s.add(
                Run(
                    id=run_id,
                    strategy_name=strategy_name,
                    mode="backtest",
                    started_at=datetime.now(UTC),
                    config_json=json.dumps(
                        {
                            "params": params,
                            "start": start.isoformat(),
                            "end": end.isoformat(),
                        }
                    ),
                )
            )
            s.commit()

        start_dt = datetime.combine(start, time.min, tzinfo=UTC)
        end_dt = datetime.combine(end, time.min, tzinfo=UTC)
        _run_alpaca_backtest(REGISTRY[strategy_name], start_dt, end_dt, params)
    finally:
        engine.dispose()
