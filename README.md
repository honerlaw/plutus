# Plutus

A Python lab for running multiple deterministic intraday and swing trading strategies side-by-side against an **Alpaca paper trading** account. Every signal each strategy emits — and every order Alpaca fills — is recorded to a local SQLite database so the strategies can be compared against each other over time on identical market conditions.

**This is a research tool. It is paper-only. There are no live-money code paths anywhere in the repo.**

## What it does

Three strategies, one per family, all deterministic and parameterised in `configs/universe.yaml`:

| Name | Family | Horizon | Logic |
|---|---|---|---|
| `orb` | Trend / momentum | Intraday (1-min) | Opening Range Breakout — long above the first 15 min high, short below the low, EOD exit |
| `rsi_vwap` | Mean reversion | Intraday (5-min) | RSI(14) below 30 and price below session VWAP → long; above 70 and above VWAP → short; exit when RSI crosses 50 |
| `donchian_swing` | Breakout | Swing (1-hour bars, holds 1–5 days) | Donchian channel break with ATR trailing stop and a max-hold cap |

Each runs on the same universe (`SPY, QQQ, AAPL, MSFT, NVDA, TSLA, AMD, META`) and writes its signals to `./data/plutus.db`.

## Quick start

Secrets are provided by [Doppler](https://doppler.com). Set up the CLI, then:

```bash
# 1. Install deps
uv sync

# 2. Start the web server (signals + report via HTTP)
doppler run -- uvicorn plutus.web:app --reload
# → http://localhost:8000/strategies
# → http://localhost:8000/signals
# → http://localhost:8000/report
# → http://localhost:8000/health

# 3. Start the paper trader (background worker, blocks)
doppler run -- uv run plutus run

# 4. Or backtest one strategy
doppler run -- uv run plutus backtest --strategy orb \
  --start 2026-01-01 --end 2026-04-30
```

**Without Doppler** — export vars manually:

```bash
export ALPACA_API_KEY=...
export ALPACA_API_SECRET=...
export PLUTUS_DB_URL=postgresql://user:pass@localhost/plutus
# For local SQLite: export PLUTUS_DB_URL=sqlite:///./data/plutus.db
uv run uvicorn plutus.web:app --reload
```

## Configuration

All settings arrive as environment variables (injected by Doppler in production). The `ALPACA_PAPER` flag is **forced to `True` by the Settings validator** — paper trading is a hard invariant of this project.

```
ALPACA_API_KEY=...
ALPACA_API_SECRET=...
PLUTUS_DB_URL=postgresql+psycopg://user:pass@host/dbname   # psycopg3 driver — +psycopg required
PLUTUS_SUBMIT_ORDERS=true   # false = log signals only, skip broker submission
PLUTUS_LOG_LEVEL=INFO
```

> **Important:** `PLUTUS_DB_URL` must use the `postgresql+psycopg://` scheme (not `postgresql://`) to route through the installed psycopg3 driver. Using `postgresql://` will fall back to psycopg2.

Strategy parameters and the universe live in `configs/universe.yaml`. Disable a strategy by flipping its `enabled: true` → `false`.

## Project layout

```
src/plutus/
├─ config.py           # pydantic-settings; ALPACA_PAPER forced True
├─ logging.py          # structlog setup, run_id binding
├─ broker.py           # Alpaca paper broker factory (PAPER: True hard-coded)
├─ storage/
│  ├─ models.py        # Run, Signal, Order, DailyRunSummary (SQLModel)
│  └─ db.py            # init_db, session_scope
├─ strategies/
│  ├─ base.py          # ProposedSignal + SignalRecorder (the only DB-writer for signals)
│  ├─ registry.py      # @register decorator + load_enabled
│  ├─ indicators.py    # rsi, vwap, donchian, atr (pure functions)
│  ├─ orb.py           # Opening Range Breakout — pure signal logic
│  ├─ rsi_vwap.py      # RSI + VWAP mean reversion — pure signal logic
│  ├─ donchian_swing.py# Donchian swing breakout — pure signal logic
│  └─ adapter.py       # lumibot Strategy wrappers around the pure layer
├─ universe.py         # YAML loader
├─ runner.py           # Builds Trader, attaches strategies, writes Run rows
├─ backtest.py         # Single-strategy backtest entry
├─ report.py           # DB aggregations
└─ cli.py              # typer entry point
```

Pure signal logic and DB/broker integration are deliberately kept in separate files so the strategy logic is trivially unit-testable without lumibot or Alpaca.

## Tooling

Strict by design:

- **Lint:** `uv run ruff check` (`select = ["ALL"]`)
- **Format:** `uv run ruff format`
- **Type check:** `uv run ty check`
- **Tests:** `uv run pytest` (`-W error`, 85% coverage gate)
- **Pre-commit:** `uv run pre-commit run --all-files` (ruff + ty + uv-lock + `paper=False` grep)
- **CI:** GitHub Actions runs the full set on every push and PR

See `AGENTS.md` for the full rules — agents (including Claude Code) follow them strictly.

## Known limitations (initial implementation)

This is the first cut. Two intentional gaps to address as follow-ups:

1. **Live bar fetching is stubbed.** The `_fetch_bars_*` methods in `adapter.py` currently return `[]`, so `plutus run` will not emit signals against a real Alpaca paper account until `lumibot.Strategy.get_historical_prices` is wired in. The pure signal logic is fully tested and works — only the data-source plumbing is missing.
2. **`hit_rate` and `pnl(paper)` not yet computed.** `report.py` reports signal/fill counts and average slippage. The `DailyRunSummary` table exists but nothing writes to it yet (needs an `after_market_closes` hook on the adapter). Backtests will run, but the comparison metrics in the spec are partial.

`plutus backtest` works against `lumibot`'s `AlpacaBacktesting` (assuming you have Alpaca historical-bar access) once you fill in the bar-fetching gap above.

## Safety

- Alpaca is constructed with `PAPER: True` in `src/plutus/broker.py`. That line is **not parameterised**. A pre-commit hook greps `src/` for `paper=False` and rejects the commit if it ever appears.
- The `Settings._force_paper` validator overrides `ALPACA_PAPER` from the environment to `True`. Even setting `ALPACA_PAPER=false` in `.env` is ignored.
- Real credentials live in `.env` (gitignored). Only `.env.example` is committed.

## License

No license declared yet. Treat as "all rights reserved" until one is added.
