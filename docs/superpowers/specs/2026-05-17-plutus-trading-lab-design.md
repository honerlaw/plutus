# Plutus — Paper-signal Trading Lab

**Status:** Approved
**Date:** 2026-05-17
**Owner:** @honerlawd

## Purpose

A local Python lab that runs several deterministic intraday and swing trading strategies side-by-side against Alpaca's paper-trading account and records every signal and resulting order to a local SQLite database. The point is to compare strategies against each other over time using identical market conditions — not to make money, not to claim any signal is production-ready.

Hard constraints:

- **Paper money only.** No live brokerage credentials anywhere in the codebase or config.
- **Strict tooling.** Ruff (`select = ["ALL"]`), `ty` strict, pytest with warnings as errors, pre-commit, CI.
- **Strategies are deterministic.** No ML, no online learning. Same input → same signal, every time.

## Non-goals

- Production trading or order routing
- Real-money risk management
- Multi-asset coverage (equities only)
- Options, futures, crypto
- A web UI or dashboard (deferred until we have a month of data)
- Notifications (Slack/Discord) (deferred)
- Walk-forward, parameter sweeps, ML (deferred)

## User-facing behavior

A single CLI, `plutus`, with these subcommands:

| Command | Behavior |
|---|---|
| `plutus run` | Start the lumibot `Trader` with all enabled strategies against Alpaca paper. Blocks. |
| `plutus backtest --strategy <name> --start <date> --end <date>` | Run one strategy on historical Alpaca minute bars; record to a separate `runs` row with `mode=backtest`. |
| `plutus list` | Print the registered strategies, their family, horizon, and default config. |
| `plutus signals [--strategy <name>] [--since <date>]` | Print recent signals from the DB as a table. |
| `plutus report [--since <date>]` | Print per-strategy summary: count of signals, hit rate, avg slippage, hypothetical PnL since `--since`. |

Secrets come from a `.env` file (committed `.env.example`, real `.env` in `.gitignore`):

```
ALPACA_API_KEY=...
ALPACA_API_SECRET=...
ALPACA_PAPER=true
PLUTUS_SUBMIT_ORDERS=true   # if false, log signals only, skip broker submission
PLUTUS_DB_PATH=./data/plutus.db
PLUTUS_LOG_LEVEL=INFO
```

## Architecture

```
plutus/
├─ pyproject.toml
├─ uv.lock
├─ AGENTS.md                       # strict tooling rules
├─ CLAUDE.md                       # symlink -> AGENTS.md
├─ .env.example
├─ .gitignore                      # .env, data/, .venv/, __pycache__/, .ruff_cache/, .pytest_cache/
├─ .pre-commit-config.yaml
├─ .github/workflows/ci.yml
├─ configs/
│  └─ universe.yaml                # symbols, per-strategy enable flags, allocations
├─ docs/superpowers/specs/         # this file
├─ src/plutus/
│  ├─ __init__.py
│  ├─ config.py                    # pydantic-settings; loads .env
│  ├─ logging.py                   # structlog setup, run_id binding
│  ├─ broker.py                    # Alpaca paper broker factory
│  ├─ storage/
│  │  ├─ __init__.py
│  │  ├─ db.py                     # SQLite engine, session factory, migrations
│  │  └─ models.py                 # sqlmodel: Run, Signal, Order, DailyRunSummary
│  ├─ strategies/
│  │  ├─ __init__.py
│  │  ├─ base.py                   # PlutusStrategy(lumibot.Strategy)
│  │  ├─ registry.py               # name -> class map; load_enabled(config) helper
│  │  ├─ orb.py                    # Opening Range Breakout (baseline)
│  │  ├─ rsi_vwap.py               # RSI(14) on 5m + VWAP filter
│  │  └─ donchian_swing.py         # Donchian(20) on 1h, ATR trailing stop
│  ├─ runner.py                    # build Trader, attach strategies, run live paper
│  ├─ backtest.py                  # AlpacaBacktesting wiring
│  ├─ report.py                    # aggregations over the DB for `plutus report`
│  └─ cli.py                       # typer app entrypoint
└─ tests/
   ├─ conftest.py
   ├─ test_storage.py
   ├─ test_registry.py
   ├─ strategies/
   │  ├─ test_orb.py
   │  ├─ test_rsi_vwap.py
   │  └─ test_donchian_swing.py
   └─ test_report.py
```

### `PlutusStrategy` base class

A thin subclass of `lumibot.strategies.Strategy` that all our strategies inherit from. Responsibilities:

- Bind a `run_id` (UUID, created at `initialize`) and store the `Run` row.
- Override `create_order` (or wrap order creation): every time the concrete strategy decides to place an order, write a `Signal` row *first*, then either submit to the broker and write an `Order` row, or skip submission if `PLUTUS_SUBMIT_ORDERS=false`.
- Record indicator values that drove the signal in `Signal.indicator_values_json` so the report can explain *why* later.
- On `after_market_closes`, write a `DailyRunSummary` row aggregating the day's activity (signal count, fill count, realized PnL on closed positions, open position count).
- Provide subclasses with hooks: `compute_signals(bars) -> list[ProposedSignal]` and `horizon: Literal["intraday","swing"]`, `max_hold_bars: int`. The base class is responsible for translating `ProposedSignal` into orders and DB rows.

This is the only place that touches both lumibot's order API and the DB — concrete strategies stay pure.

### Strategy registry

`registry.py` exports `REGISTRY: dict[str, type[PlutusStrategy]]`. Strategies register themselves via a decorator:

```python
@register("orb")
class OpeningRangeBreakout(PlutusStrategy):
    ...
```

`load_enabled(config)` reads `configs/universe.yaml`, returns instantiated strategy objects with their per-strategy config.

### Storage schema

SQLite via `sqlmodel`. File at `PLUTUS_DB_PATH` (default `./data/plutus.db`). Schema migrations: bootstrap via `SQLModel.metadata.create_all()` on first run. (No alembic until we need it.)

```python
class Run(SQLModel, table=True):
    id: UUID                      # primary key
    strategy_name: str
    mode: Literal["paper", "backtest"]
    started_at: datetime
    ended_at: datetime | None
    config_json: str              # serialized strategy config + universe slice

class Signal(SQLModel, table=True):
    id: int                       # autoincrement PK
    run_id: UUID                  # FK -> Run
    strategy_name: str
    timestamp: datetime           # bar timestamp that produced the signal
    symbol: str
    side: Literal["buy", "sell"]
    qty: float
    signal_type: Literal["entry", "exit", "stop", "take_profit"]
    price_at_signal: float        # last close at signal time
    stop_price: float | None
    take_profit_price: float | None
    indicator_values_json: str    # e.g. {"rsi": 28.4, "vwap": 412.10}

class Order(SQLModel, table=True):
    id: int                       # autoincrement PK
    run_id: UUID                  # FK -> Run
    signal_id: int                # FK -> Signal
    alpaca_order_id: str | None   # null if PLUTUS_SUBMIT_ORDERS=false
    status: str                   # "submitted" | "filled" | "rejected" | "canceled" | "skipped"
    filled_price: float | None
    filled_qty: float | None
    submitted_at: datetime
    filled_at: datetime | None

class DailyRunSummary(SQLModel, table=True):
    id: int                       # autoincrement PK
    run_id: UUID                  # FK -> Run
    strategy_name: str
    trading_date: date
    signals_count: int
    orders_filled_count: int
    realized_pnl: float           # on positions closed today
    open_positions_count: int
```

Indexes: `Signal(run_id, timestamp)`, `Signal(strategy_name, timestamp)`, `Order(signal_id)`, `DailyRunSummary(strategy_name, trading_date)` unique.

### Three baseline strategies

#### 1. Opening Range Breakout (`orb`) — baseline

- Horizon: intraday. `sleeptime = "1M"`.
- Universe: liquid large-caps (`SPY, QQQ, AAPL, MSFT, NVDA, TSLA, AMD, META`).
- 9:30–9:45 ET: observe; do nothing. Record OR-high and OR-low per symbol.
- 9:45–15:55 ET: if last close > OR-high → long entry; if < OR-low → short entry. One position per symbol per day. Stop at the opposite extreme of the OR. Take-profit at 1× the OR width above entry (or below for shorts).
- 15:55 ET: exit any remaining positions.
- Position sizing: risk 0.5% of equity per trade. `qty = round(0.005 * equity / (entry - stop))`.

#### 2. RSI(14) + VWAP filter (`rsi_vwap`) — mean reversion

- Horizon: intraday. `sleeptime = "5M"`.
- Universe: same.
- Compute RSI(14) on 5-min bars. Compute session VWAP.
- Long when RSI < 30 AND price < VWAP (fading downside). Exit when RSI > 50 or end of day.
- Short when RSI > 70 AND price > VWAP. Exit when RSI < 50 or end of day.
- Stop: 1.5 × ATR(14) on 5-min bars. Position sizing: 0.5% equity risk.
- One position per symbol at a time.

#### 3. Donchian(20) swing (`donchian_swing`) — breakout

- Horizon: swing. `sleeptime = "15M"`, but only acts on bar close at the top of each hour.
- Universe: same.
- Compute Donchian channel (20-bar high/low) on hourly bars.
- Long entry on close > prior 20-bar high. Short entry on close < prior 20-bar low.
- Trailing stop at 2 × ATR(14) on hourly bars. Hard time-stop at 5 trading days.
- `max_hold_bars = 5 * 7` (≈ 5 trading days of hourly bars).

### Backtesting

`AlpacaBacktesting` from lumibot, minute-bar history for ORB/RSI strategies, hourly-bar history for Donchian. Each backtest writes a `Run` with `mode=backtest` and a unique `run_id`; signals and orders are recorded the same way as live paper. Report CLI treats backtest runs and paper runs separately (filtered by `mode`).

### Runner

`runner.py` builds an Alpaca paper broker, instantiates all enabled strategies from the registry, attaches them to a single `lumibot.traders.Trader`, and calls `.run_all()`. The trader handles the event loop; each strategy's `sleeptime` governs its own tick rate.

### Report

`plutus report` queries the DB and prints a table:

```
strategy        signals  filled  hit_rate  avg_slip(bp)  pnl(paper)   open
orb               142     128    54.7%        2.1          +$340.21    0
rsi_vwap           88      82    47.6%        3.4          -$112.40    1
donchian_swing     12       9    66.7%        1.0          +$890.15    3
```

`hit_rate` = % of *closed* round-trip trades with positive PnL. `avg_slip(bp)` = mean basis-point difference between `Signal.price_at_signal` and `Order.filled_price`. `pnl(paper)` = realized PnL on closed positions from filled orders only.

## Configuration files

### `configs/universe.yaml`

```yaml
symbols: [SPY, QQQ, AAPL, MSFT, NVDA, TSLA, AMD, META]
strategies:
  orb:
    enabled: true
    risk_per_trade: 0.005
    opening_range_minutes: 15
  rsi_vwap:
    enabled: true
    risk_per_trade: 0.005
    rsi_period: 14
    rsi_long_threshold: 30
    rsi_short_threshold: 70
  donchian_swing:
    enabled: true
    risk_per_trade: 0.005
    channel_period: 20
    atr_period: 14
    atr_multiplier: 2.0
    max_hold_bars: 35
```

## Tooling

### `pyproject.toml` (sketch)

```toml
[project]
name = "plutus"
version = "0.0.0"
requires-python = ">=3.13"
dependencies = [
    "lumibot>=3.13",
    "alpaca-py>=0.30",
    "sqlmodel>=0.0.22",
    "pydantic-settings>=2.5",
    "structlog>=24.4",
    "typer>=0.12",
    "pyyaml>=6.0",
]

[project.scripts]
plutus = "plutus.cli:app"

[tool.uv]
dev-dependencies = [
    "ruff>=0.7",
    "ty>=0.0.1a4",
    "pytest>=8.3",
    "pytest-cov>=5.0",
    "pre-commit>=4.0",
    "types-pyyaml",
]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["ALL"]
ignore = [
    "D203", "D213",   # docstring formatting conflicts
    "COM812",         # conflicts with formatter
    "ANN401",         # allow `Any` where needed
    "FIX002", "TD002", "TD003",  # tolerate TODO comments
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "D", "ANN", "PLR2004"]  # pytest assertions, no docstrings required

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ty]
strict = true
src = ["src", "tests"]

[tool.pytest.ini_options]
addopts = "-W error -ra --cov=plutus --cov-fail-under=85"
testpaths = ["tests"]
```

### `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/astral-sh/ty-pre-commit
    rev: v0.0.1a4
    hooks:
      - id: ty
  - repo: https://github.com/astral-sh/uv-pre-commit
    rev: 0.5.0
    hooks:
      - id: uv-lock
```

### `AGENTS.md` (symlinked from `CLAUDE.md`)

Must explicitly state:

- All code must pass `ruff check` with `select = ["ALL"]` and the documented ignore list — no per-line `# noqa` without a comment explaining why.
- All code must pass `ty --strict` — no untyped functions, no untyped calls, no implicit `Any`.
- All tests run with `pytest -W error` — warnings are failures.
- Coverage gate is 85% on `src/plutus`.
- No real Alpaca credentials in any committed file, ever. `.env.example` only.
- No live-trading code paths. Alpaca client is constructed with `paper=True`, hard-coded.
- Pre-commit hooks must pass locally before pushing; CI re-runs them.

### CI

GitHub Actions `.github/workflows/ci.yml`: on every push and PR, run `uv sync`, `pre-commit run --all-files`, `pytest`. Matrix on Python 3.13 only.

## Testing strategy

- **Unit tests** for each strategy: feed synthetic bar data through `compute_signals` and assert the exact signals produced. Strategies are deterministic, so these are pure functions.
- **Storage tests**: in-memory SQLite, create/read each model, exercise the indexes.
- **Registry tests**: register a fake strategy, load via `load_enabled`, assert config flows through.
- **Report tests**: seed DB with known runs/signals/orders, assert aggregation math.
- **No live broker tests.** lumibot's broker is mocked at the boundary.

TDD: each strategy gets its tests written before the strategy itself (or alongside, in the same commit).

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Alpaca free IEX feed has gaps / partial volume | Document in README; lab is for strategy *comparison*, not absolute performance. |
| PDT rule blocks day trades on paper account < $25k | Set Alpaca paper equity to $100k in the Alpaca dashboard; document in setup. |
| `ty` is pre-1.0 and may have rough edges | Pin a specific version in pre-commit; pin in `uv.lock`. Tolerate breakage; upgrade deliberately. |
| Strategy bug submits real money | Hard-coded `paper=True` in broker factory; no env var override; CI grep test fails build if `paper=False` appears in source. |
| SQLite file grows unbounded over months | Acceptable for now (a year of minute signals across 8 symbols × 3 strategies is still small). Revisit when DB > 1 GB. |

## Open items (resolved during brainstorm)

- Storage: **SQLite + sqlmodel.**
- Schedule: **lumibot built-in, per-strategy `sleeptime`.**
- CLI: **typer.**
- Order submission: **paper broker + DB record by default; `PLUTUS_SUBMIT_ORDERS=false` to skip broker.**
- Python: **3.13.**
- Universe: **`SPY, QQQ, AAPL, MSFT, NVDA, TSLA, AMD, META`.**
- Baseline algo: **Opening Range Breakout.**

## Out of scope for this spec (future work)

- HTML or Streamlit dashboard
- Notifications
- Walk-forward analysis, parameter sweeps
- Postgres / cloud DB
- Options, futures, crypto
- Polygon or other paid data feeds
- ML-based strategies
