"""Typer CLI: `plutus run | backtest | list | signals | report`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer
from sqlmodel import Session, select

import plutus.strategies  # noqa: F401 -- registers all strategies
from plutus.config import Settings
from plutus.report import build_summary
from plutus.storage import Signal, init_db
from plutus.strategies.registry import REGISTRY

app = typer.Typer(help="Plutus paper trading lab.")

DEFAULT_UNIVERSE = Path("configs/universe.yaml")


@app.command(name="list")
def list_strategies() -> None:
    """List registered strategies."""
    for name in sorted(REGISTRY):
        typer.echo(name)


@app.command(name="run")
def cmd_run(
    universe: Annotated[Path, typer.Option(help="Universe YAML path")] = DEFAULT_UNIVERSE,
) -> None:
    """Run all enabled strategies against Alpaca paper. Blocks."""
    from plutus.runner import run_paper

    run_paper(universe_path=universe)


@app.command(name="backtest")
def cmd_backtest(
    strategy: Annotated[str, typer.Option(help="Strategy name")],
    start: Annotated[datetime, typer.Option(formats=["%Y-%m-%d"])],
    end: Annotated[datetime, typer.Option(formats=["%Y-%m-%d"])],
    universe: Annotated[Path, typer.Option(help="Universe YAML path")] = DEFAULT_UNIVERSE,
) -> None:
    """Run one strategy in backtest mode against Alpaca historical bars."""
    from plutus.backtest import run_backtest

    run_backtest(
        strategy_name=strategy,
        start=start.date(),
        end=end.date(),
        universe_path=universe,
    )


@app.command(name="signals")
def cmd_signals(
    strategy: Annotated[str | None, typer.Option(help="Filter by strategy")] = None,
    since: Annotated[
        datetime | None,
        typer.Option(formats=["%Y-%m-%d"], help="Default: last 7 days"),
    ] = None,
) -> None:
    """Print recent signals from the DB."""
    settings = Settings()
    engine = init_db(settings.database_url)
    try:
        cutoff = since or (datetime.now(UTC) - timedelta(days=7))
        with Session(engine) as s:
            stmt = select(Signal).where(Signal.timestamp >= cutoff)
            if strategy is not None:
                stmt = stmt.where(Signal.strategy_name == strategy)
            rows = s.exec(  # type: ignore[call-overload]
                stmt.order_by(Signal.timestamp.desc()).limit(100)  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
            ).all()
        if not rows:
            typer.echo("No signals.")
            return
        typer.echo(
            f"{'strategy':<18} {'time':<25} {'symbol':<6} {'side':<5} {'type':<14} qty   price"
        )
        for r in rows:
            typer.echo(
                f"{r.strategy_name:<18} {r.timestamp.isoformat():<25} {r.symbol:<6} "
                f"{r.side:<5} {r.signal_type:<14} {r.qty:<5} {r.price_at_signal}"
            )
    finally:
        engine.dispose()


@app.command(name="report")
def cmd_report(
    since: Annotated[
        datetime | None,
        typer.Option(formats=["%Y-%m-%d"], help="Default: last 30 days"),
    ] = None,
) -> None:
    """Per-strategy summary."""
    settings = Settings()
    engine = init_db(settings.database_url)
    try:
        cutoff = since or (datetime.now(UTC) - timedelta(days=30))
        rows = build_summary(engine, since=cutoff)
        if not rows:
            typer.echo("No data.")
            return
        typer.echo(f"{'strategy':<18} {'signals':>8} {'filled':>8} {'avg_slip(bp)':>14}")
        for r in rows:
            slip = f"{r.avg_slip_bp:.2f}" if r.avg_slip_bp is not None else "-"
            typer.echo(f"{r.strategy:<18} {r.signals:>8} {r.filled:>8} {slip:>14}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    app()
