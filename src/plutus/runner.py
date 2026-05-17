"""Wires Alpaca broker, strategies, DB, and lumibot Trader together."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from lumibot.traders import Trader
from sqlmodel import Session

import plutus.strategies  # noqa: F401 -- side-effect: registers all strategies
from plutus.broker import make_paper_broker
from plutus.config import Settings
from plutus.logging import bind_run_id, configure_logging
from plutus.storage import Run, init_db
from plutus.strategies.registry import load_enabled
from plutus.universe import load_universe

if TYPE_CHECKING:
    from pathlib import Path

    from plutus.strategies.adapter import _PlutusAdapter


@dataclass
class RunnerBundle:
    """Holds the wired-up Trader, strategy adapters, and per-strategy run UUIDs."""

    trader: Trader
    strategies: list[_PlutusAdapter]
    run_ids: dict[str, UUID]


def build_runner(*, universe_path: Path) -> RunnerBundle:
    """Construct the lumibot Trader and attach all enabled plutus strategies."""
    settings = Settings()
    configure_logging(settings.log_level)
    engine = init_db(settings.db_path)
    broker = make_paper_broker(settings)
    trader = Trader()

    universe = load_universe(universe_path)
    strategies = load_enabled(universe)
    run_ids: dict[str, UUID] = {}

    for strat in strategies:
        run_id = uuid4()
        run_ids[strat._registry_name] = run_id  # noqa: SLF001
        with Session(engine) as s:
            s.add(
                Run(
                    id=run_id,
                    strategy_name=strat._registry_name,  # noqa: SLF001
                    mode="paper",
                    started_at=datetime.now(UTC),
                    config_json=json.dumps(strat._kwargs),  # noqa: SLF001
                )
            )
            s.commit()
        strat.attach_engine(engine=engine, run_id=run_id, submit=settings.submit_orders)
        # Get a real lumibot Strategy from the adapter and add THAT to the Trader.
        lumibot_strat = strat.to_lumibot_strategy(broker)
        trader.add_strategy(lumibot_strat)
        bind_run_id(str(run_id), strategy_name=strat._registry_name).info(  # noqa: SLF001
            "runner.strategy_attached"
        )

    return RunnerBundle(trader=trader, strategies=strategies, run_ids=run_ids)


def run_paper(*, universe_path: Path) -> None:
    """Build the runner and start the trader's event loop. Blocks."""
    bundle = build_runner(universe_path=universe_path)
    bundle.trader.run_all()
