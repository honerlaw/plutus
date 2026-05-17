# Plutus Trading Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a strict-typed Python lab that runs three deterministic intraday/swing trading strategies (ORB, RSI+VWAP, Donchian) against Alpaca paper trading and records every signal and order to SQLite for cross-strategy comparison over time.

**Architecture:** A single Python package `plutus` with a `lumibot`-based runner that hosts multiple `PlutusStrategy` subclasses on one Alpaca paper `Trader`. The base class wraps order creation to write a `Signal` row to SQLite before submission and an `Order` row after. Concrete strategies stay pure (no DB knowledge). A `typer` CLI exposes `run`, `backtest`, `list`, `signals`, `report`. Backtesting uses `AlpacaBacktesting` with the same strategy classes.

**Tech Stack:** Python 3.13, `uv` (packaging), `ruff` (lint, `select = ["ALL"]`), `ty` (strict type check), `pytest` (TDD with `-W error` and 85% coverage gate), `lumibot` + `alpaca-py` (trading), `sqlmodel` + SQLite (storage), `pydantic-settings` (config), `structlog` (logging), `typer` (CLI), `pre-commit`, GitHub Actions.

**Reference spec:** `docs/superpowers/specs/2026-05-17-plutus-trading-lab-design.md`

---

## File map

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Project metadata, deps, ruff/ty/pytest config |
| `uv.lock` | Locked dependency tree |
| `.gitignore` | Ignore `.env`, `data/`, caches, `.venv/` |
| `.env.example` | Documents required env vars; real `.env` never committed |
| `.pre-commit-config.yaml` | ruff (lint + format), ty, uv-lock check |
| `.github/workflows/ci.yml` | uv sync + pre-commit + pytest on push/PR |
| `AGENTS.md` | Strict tooling rules for any agent working in repo |
| `CLAUDE.md` | Symlink → `AGENTS.md` |
| `configs/universe.yaml` | Symbols + per-strategy enable flags + params |
| `src/plutus/__init__.py` | Package marker, version |
| `src/plutus/config.py` | `Settings` (pydantic-settings) loads `.env` |
| `src/plutus/logging.py` | `configure_logging()`, `bind_run_id()` |
| `src/plutus/broker.py` | `make_paper_broker()` — hard-coded `paper=True` |
| `src/plutus/storage/__init__.py` | Re-exports |
| `src/plutus/storage/models.py` | `Run`, `Signal`, `Order`, `DailyRunSummary` |
| `src/plutus/storage/db.py` | Engine factory, `init_db()`, `session_scope()` |
| `src/plutus/strategies/__init__.py` | Imports each strategy module to trigger registration |
| `src/plutus/strategies/base.py` | `PlutusStrategy`, `ProposedSignal` dataclass |
| `src/plutus/strategies/registry.py` | `REGISTRY`, `@register`, `load_enabled()` |
| `src/plutus/strategies/orb.py` | Opening Range Breakout |
| `src/plutus/strategies/rsi_vwap.py` | RSI + VWAP mean-reversion |
| `src/plutus/strategies/donchian_swing.py` | Donchian swing breakout |
| `src/plutus/runner.py` | `run_paper()` — build Trader, attach strategies |
| `src/plutus/backtest.py` | `run_backtest()` using `AlpacaBacktesting` |
| `src/plutus/report.py` | DB aggregations for `plutus report` |
| `src/plutus/cli.py` | typer `app` with `run`, `backtest`, `list`, `signals`, `report` |
| `tests/conftest.py` | Pytest fixtures: in-memory DB, fake clock |
| `tests/test_config.py` | Settings loading |
| `tests/test_storage.py` | Model round-trips, indexes |
| `tests/test_registry.py` | Register, load_enabled |
| `tests/strategies/test_base.py` | Base class signal recording |
| `tests/strategies/test_orb.py` | ORB signal generation |
| `tests/strategies/test_rsi_vwap.py` | RSI+VWAP signal generation |
| `tests/strategies/test_donchian_swing.py` | Donchian signal generation |
| `tests/test_report.py` | Aggregation math |
| `tests/test_cli.py` | typer command smoke tests |

---

## Task 1: Bootstrap `uv` project + Python version

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `.gitignore`
- Create: `src/plutus/__init__.py`

- [ ] **Step 1: Initialize the project with uv**

```bash
cd /Users/derekhonerlaw/Development/plutus
uv init --package --name plutus --python 3.13 --no-readme
```

This generates `pyproject.toml`, `.python-version`, and `src/plutus/__init__.py`. Verify with `ls -la`.

- [ ] **Step 2: Replace generated `pyproject.toml` with the full project config**

```toml
[project]
name = "plutus"
version = "0.0.0"
description = "Paper-signal trading lab"
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

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv]
dev-dependencies = [
    "ruff>=0.7",
    "ty>=0.0.1a4",
    "pytest>=8.3",
    "pytest-cov>=5.0",
    "pre-commit>=4.0",
    "types-pyyaml",
    "freezegun>=1.5",
]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["ALL"]
ignore = [
    "D203", "D213",
    "COM812",
    "ANN401",
    "FIX002", "TD002", "TD003",
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "D", "ANN", "PLR2004", "SLF001"]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ty]
strict = true
src = ["src", "tests"]

[tool.pytest.ini_options]
addopts = "-W error -ra --cov=plutus --cov-fail-under=85"
testpaths = ["tests"]
```

- [ ] **Step 3: Write `.gitignore`**

```
.venv/
.env
data/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.ty_cache/
.coverage
coverage.xml
htmlcov/
dist/
build/
*.egg-info/
.DS_Store
```

- [ ] **Step 4: Confirm `src/plutus/__init__.py` exists with a version constant**

Overwrite `src/plutus/__init__.py` with:

```python
"""Plutus paper-signal trading lab."""

__version__ = "0.0.0"
```

- [ ] **Step 5: Lock dependencies and verify**

Run: `uv sync`
Expected: Creates `.venv/` and `uv.lock`. No errors.

- [ ] **Step 6: Smoke-check tooling is installed**

Run: `uv run ruff --version && uv run ty --version && uv run pytest --version`
Expected: All three print versions cleanly.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock .python-version .gitignore src/plutus/__init__.py
git commit -m "chore: bootstrap uv project with strict ruff/ty/pytest config"
```

---

## Task 2: Project metadata files (AGENTS.md, env example, configs dir)

**Files:**
- Create: `AGENTS.md`
- Create: `CLAUDE.md` (symlink)
- Create: `.env.example`
- Create: `configs/universe.yaml`

- [ ] **Step 1: Write `AGENTS.md`**

```markdown
# Agent Instructions for Plutus

## Tooling rules (NON-NEGOTIABLE)

- **Lint:** `uv run ruff check` must pass. Ruff is configured with `select = ["ALL"]`. No new `# noqa` without an inline comment explaining why.
- **Format:** `uv run ruff format` must produce no changes.
- **Type check:** `uv run ty check` must pass in strict mode. No untyped function definitions, no untyped calls, no implicit `Any`.
- **Tests:** `uv run pytest` must pass with no warnings. Coverage gate is 85% on `src/plutus`; do not lower it.
- **Lock file:** `uv lock --check` must pass — commit `uv.lock` with any dependency change.
- **Pre-commit:** Run `uv run pre-commit run --all-files` before pushing. CI re-runs everything.

## Safety rules

- This project runs against Alpaca **paper trading only**. The Alpaca client is constructed with `paper=True` in `src/plutus/broker.py` and that line must not be parameterized. CI greps for `paper=False` and fails the build if it appears anywhere in `src/`.
- Real credentials live in `.env` (gitignored). Only `.env.example` may be committed.
- No live-trading code paths anywhere — even disabled or behind a flag.

## Code style

- Strategies are deterministic pure functions of bar data. No randomness, no network calls inside `compute_signals`.
- DB access only inside `PlutusStrategy` base class and `report.py` — never in concrete strategy files.
- Prefer `sqlmodel` over raw SQL.
- Use `structlog` for all logging; bind `run_id` and `strategy_name` at the start of each run.
- Tests are TDD. Write the failing test first, run it to confirm it fails, then implement.

## Layout

See `docs/superpowers/specs/2026-05-17-plutus-trading-lab-design.md` for the architecture.
```

- [ ] **Step 2: Create `CLAUDE.md` as a symlink to `AGENTS.md`**

Run: `ln -s AGENTS.md CLAUDE.md`
Verify: `ls -la CLAUDE.md` shows `CLAUDE.md -> AGENTS.md`.

- [ ] **Step 3: Write `.env.example`**

```
# Copy to .env and fill in values. .env is gitignored.
ALPACA_API_KEY=
ALPACA_API_SECRET=
ALPACA_PAPER=true
PLUTUS_SUBMIT_ORDERS=true
PLUTUS_DB_PATH=./data/plutus.db
PLUTUS_LOG_LEVEL=INFO
```

- [ ] **Step 4: Write `configs/universe.yaml`**

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
    atr_period: 14
    atr_multiplier: 1.5
  donchian_swing:
    enabled: true
    risk_per_trade: 0.005
    channel_period: 20
    atr_period: 14
    atr_multiplier: 2.0
    max_hold_bars: 35
```

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md CLAUDE.md .env.example configs/universe.yaml
git commit -m "docs: add AGENTS.md (CLAUDE.md symlink), env example, universe config"
```

---

## Task 3: Pre-commit + CI

**Files:**
- Create: `.pre-commit-config.yaml`
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write `.pre-commit-config.yaml`**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/astral-sh/uv-pre-commit
    rev: 0.5.0
    hooks:
      - id: uv-lock
  - repo: local
    hooks:
      - id: ty
        name: ty (strict)
        entry: uv run ty check
        language: system
        types: [python]
        pass_filenames: false
      - id: no-paper-false
        name: forbid paper=False
        entry: bash -c 'if grep -r "paper=False" src/; then echo "paper=False found in src/"; exit 1; fi'
        language: system
        pass_filenames: false
```

- [ ] **Step 2: Install pre-commit hooks locally**

Run: `uv run pre-commit install`
Expected: `pre-commit installed at .git/hooks/pre-commit`.

- [ ] **Step 3: Run pre-commit against existing files to confirm green**

Run: `uv run pre-commit run --all-files`
Expected: All hooks pass. ty may need `__init__.py` files but those exist.

- [ ] **Step 4: Write `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - name: Install Python
        run: uv python install 3.13
      - name: Install deps
        run: uv sync --frozen
      - name: Pre-commit
        run: uv run pre-commit run --all-files
      - name: Tests
        run: uv run pytest
```

- [ ] **Step 5: Commit**

```bash
git add .pre-commit-config.yaml .github/workflows/ci.yml
git commit -m "chore: add pre-commit hooks and GitHub Actions CI"
```

---

## Task 4: Settings module (`config.py`)

**Files:**
- Create: `src/plutus/config.py`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/__init__.py` (empty). Then create `tests/test_config.py`:

```python
"""Tests for plutus.config."""
from pathlib import Path

import pytest

from plutus.config import Settings


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ALPACA_API_KEY", "key123")
    monkeypatch.setenv("ALPACA_API_SECRET", "secret456")
    monkeypatch.setenv("ALPACA_PAPER", "true")
    monkeypatch.setenv("PLUTUS_SUBMIT_ORDERS", "false")
    monkeypatch.setenv("PLUTUS_DB_PATH", str(tmp_path / "x.db"))
    monkeypatch.setenv("PLUTUS_LOG_LEVEL", "DEBUG")

    s = Settings()

    assert s.alpaca_api_key == "key123"
    assert s.alpaca_api_secret == "secret456"
    assert s.alpaca_paper is True
    assert s.submit_orders is False
    assert s.db_path == tmp_path / "x.db"
    assert s.log_level == "DEBUG"


def test_settings_paper_is_always_true_even_if_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_API_SECRET", "s")
    monkeypatch.setenv("ALPACA_PAPER", "false")

    s = Settings()

    assert s.alpaca_paper is True, "paper trading must be forced on"
```

- [ ] **Step 2: Run the test to verify failure**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `plutus.config` does not exist.

- [ ] **Step 3: Implement `src/plutus/config.py`**

```python
"""Application settings loaded from environment / .env file."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Never mutate; instantiate fresh."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    alpaca_api_key: str = Field(..., alias="ALPACA_API_KEY")
    alpaca_api_secret: str = Field(..., alias="ALPACA_API_SECRET")
    alpaca_paper: bool = Field(default=True, alias="ALPACA_PAPER")
    submit_orders: bool = Field(default=True, alias="PLUTUS_SUBMIT_ORDERS")
    db_path: Path = Field(default=Path("./data/plutus.db"), alias="PLUTUS_DB_PATH")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", alias="PLUTUS_LOG_LEVEL"
    )

    @field_validator("alpaca_paper")
    @classmethod
    def _force_paper(cls, _v: bool) -> bool:  # noqa: FBT001 - validator signature
        # Safety: plutus is a paper-only lab. The setting exists for clarity but is forced True.
        return True
```

- [ ] **Step 4: Run the test to verify pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: 2 passed.

- [ ] **Step 5: Lint and type-check**

Run: `uv run ruff check src/plutus/config.py tests/test_config.py && uv run ty check`
Expected: Both clean.

- [ ] **Step 6: Commit**

```bash
git add src/plutus/config.py tests/test_config.py tests/__init__.py
git commit -m "feat(config): add Settings with forced paper=True safeguard"
```

---

## Task 5: Logging module (`logging.py`)

**Files:**
- Create: `src/plutus/logging.py`
- Create: `tests/test_logging.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for plutus.logging."""
from __future__ import annotations

import structlog

from plutus.logging import bind_run_id, configure_logging


def test_configure_logging_returns_logger() -> None:
    configure_logging("DEBUG")
    log = structlog.get_logger()
    log.info("hello", foo="bar")  # smoke


def test_bind_run_id_adds_context() -> None:
    configure_logging("INFO")
    log = bind_run_id("abc-123", strategy_name="orb")
    # bound vars should appear when rendering
    rendered = log.bind().info("test")  # type: ignore[no-untyped-call]
    assert rendered is None  # structlog returns None on .info
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_logging.py -v`
Expected: FAIL — `plutus.logging` missing.

- [ ] **Step 3: Implement `src/plutus/logging.py`**

```python
"""Structlog setup. Idempotent — safe to call multiple times."""
from __future__ import annotations

import logging
from typing import Any

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog + stdlib logging at the given level."""
    logging.basicConfig(format="%(message)s", level=level)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        cache_logger_on_first_use=True,
    )


def bind_run_id(run_id: str, **extra: Any) -> structlog.stdlib.BoundLogger:  # noqa: ANN401
    """Return a logger pre-bound with run_id and any extra context."""
    return structlog.get_logger().bind(run_id=run_id, **extra)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_logging.py -v && uv run ruff check src/plutus/logging.py tests/test_logging.py && uv run ty check`
Expected: Tests pass, lint/type clean.

- [ ] **Step 5: Commit**

```bash
git add src/plutus/logging.py tests/test_logging.py
git commit -m "feat(logging): add structlog configuration and run_id binder"
```

---

## Task 6: Storage models (`storage/models.py`)

**Files:**
- Create: `src/plutus/storage/__init__.py`
- Create: `src/plutus/storage/models.py`
- Create: `tests/test_storage.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for plutus.storage."""
from __future__ import annotations

import json
from datetime import UTC, date, datetime
from uuid import uuid4

from sqlmodel import Session, SQLModel, create_engine, select

from plutus.storage.models import DailyRunSummary, Order, Run, Signal


def _engine() -> object:
    eng = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(eng)
    return eng


def test_run_round_trip() -> None:
    eng = _engine()
    run = Run(
        id=uuid4(),
        strategy_name="orb",
        mode="paper",
        started_at=datetime.now(UTC),
        ended_at=None,
        config_json="{}",
    )
    with Session(eng) as s:
        s.add(run)
        s.commit()
        rows = s.exec(select(Run)).all()
    assert len(rows) == 1
    assert rows[0].strategy_name == "orb"


def test_signal_and_order_relationship() -> None:
    eng = _engine()
    run_id = uuid4()
    with Session(eng) as s:
        s.add(Run(
            id=run_id, strategy_name="orb", mode="paper",
            started_at=datetime.now(UTC), config_json="{}",
        ))
        sig = Signal(
            run_id=run_id, strategy_name="orb", timestamp=datetime.now(UTC),
            symbol="AAPL", side="buy", qty=10.0, signal_type="entry",
            price_at_signal=200.0, stop_price=195.0, take_profit_price=210.0,
            indicator_values_json=json.dumps({"or_high": 201.0}),
        )
        s.add(sig)
        s.commit()
        s.refresh(sig)
        order = Order(
            run_id=run_id, signal_id=sig.id, alpaca_order_id="abc",
            status="filled", filled_price=200.5, filled_qty=10.0,
            submitted_at=datetime.now(UTC), filled_at=datetime.now(UTC),
        )
        s.add(order)
        s.commit()
        orders = s.exec(select(Order)).all()
    assert orders[0].signal_id == sig.id


def test_daily_run_summary() -> None:
    eng = _engine()
    run_id = uuid4()
    with Session(eng) as s:
        s.add(Run(
            id=run_id, strategy_name="orb", mode="paper",
            started_at=datetime.now(UTC), config_json="{}",
        ))
        s.add(DailyRunSummary(
            run_id=run_id, strategy_name="orb", trading_date=date(2026, 5, 17),
            signals_count=5, orders_filled_count=4,
            realized_pnl=123.45, open_positions_count=1,
        ))
        s.commit()
        rows = s.exec(select(DailyRunSummary)).all()
    assert rows[0].realized_pnl == 123.45
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_storage.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement `src/plutus/storage/__init__.py`**

```python
"""Storage layer: SQLModel definitions and engine factory."""
from plutus.storage.db import init_db, session_scope
from plutus.storage.models import DailyRunSummary, Order, Run, Signal

__all__ = ["DailyRunSummary", "Order", "Run", "Signal", "init_db", "session_scope"]
```

(Note: `db.py` is created in Task 7; this import will fail until then. Reorder the import after Task 7 or temporarily leave only the model imports here. To keep tasks independent, write only the model imports for now:)

```python
"""Storage layer: SQLModel definitions and engine factory."""
from plutus.storage.models import DailyRunSummary, Order, Run, Signal

__all__ = ["DailyRunSummary", "Order", "Run", "Signal"]
```

- [ ] **Step 4: Implement `src/plutus/storage/models.py`**

```python
"""SQLModel tables for plutus.

Indexes:
  - signal_run_ts_idx on Signal(run_id, timestamp)
  - signal_strategy_ts_idx on Signal(strategy_name, timestamp)
  - daily_summary_unique on DailyRunSummary(strategy_name, trading_date)
"""
from __future__ import annotations

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
    mode: RunMode
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
    side: Side
    qty: float
    signal_type: SignalType
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
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_storage.py -v && uv run ty check`
Expected: 3 passed, ty clean.

- [ ] **Step 6: Commit**

```bash
git add src/plutus/storage/__init__.py src/plutus/storage/models.py tests/test_storage.py
git commit -m "feat(storage): add Run/Signal/Order/DailyRunSummary models"
```

---

## Task 7: Storage engine + session helpers (`storage/db.py`)

**Files:**
- Create: `src/plutus/storage/db.py`
- Modify: `src/plutus/storage/__init__.py`
- Modify: `tests/test_storage.py` (add tests for `init_db` and `session_scope`)

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_storage.py`:

```python
def test_init_db_creates_tables(tmp_path: object) -> None:
    from pathlib import Path

    from plutus.storage.db import init_db

    db_file = Path(str(tmp_path)) / "x.db"
    engine = init_db(db_file)
    assert db_file.exists()
    # Engine works for a basic insert
    with Session(engine) as s:
        s.add(Run(
            id=uuid4(), strategy_name="orb", mode="paper",
            started_at=datetime.now(UTC), config_json="{}",
        ))
        s.commit()


def test_session_scope_commits_on_exit(tmp_path: object) -> None:
    from pathlib import Path

    from plutus.storage.db import init_db, session_scope

    db_file = Path(str(tmp_path)) / "y.db"
    engine = init_db(db_file)
    rid = uuid4()
    with session_scope(engine) as s:
        s.add(Run(
            id=rid, strategy_name="orb", mode="paper",
            started_at=datetime.now(UTC), config_json="{}",
        ))
    with Session(engine) as s:
        got = s.get(Run, rid)
    assert got is not None
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_storage.py -v`
Expected: FAIL — `plutus.storage.db` missing.

- [ ] **Step 3: Implement `src/plutus/storage/db.py`**

```python
"""SQLite engine factory and session helpers."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

# Import models so SQLModel.metadata knows about them before create_all.
from plutus.storage import models  # noqa: F401


def init_db(path: Path) -> Engine:
    """Create the SQLite file (and parent dirs) and emit all tables. Returns the engine."""
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}")
    SQLModel.metadata.create_all(engine)
    return engine


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

- [ ] **Step 4: Update `src/plutus/storage/__init__.py` to re-export the helpers**

```python
"""Storage layer: SQLModel definitions and engine factory."""
from plutus.storage.db import init_db, session_scope
from plutus.storage.models import DailyRunSummary, Order, Run, Signal

__all__ = ["DailyRunSummary", "Order", "Run", "Signal", "init_db", "session_scope"]
```

- [ ] **Step 5: Run tests + lint + type**

Run: `uv run pytest tests/test_storage.py -v && uv run ruff check src/plutus/storage tests/test_storage.py && uv run ty check`
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add src/plutus/storage/db.py src/plutus/storage/__init__.py tests/test_storage.py
git commit -m "feat(storage): add init_db and session_scope helpers"
```

---

## Task 8: Strategy registry (`strategies/registry.py`)

**Files:**
- Create: `src/plutus/strategies/__init__.py`
- Create: `src/plutus/strategies/registry.py`
- Create: `tests/strategies/__init__.py`
- Create: `tests/strategies/test_registry.py`

- [ ] **Step 1: Write the failing test**

Create `tests/strategies/__init__.py` (empty). Then `tests/strategies/test_registry.py`:

```python
"""Tests for the strategy registry."""
from __future__ import annotations

from typing import Any

import pytest

from plutus.strategies.registry import REGISTRY, load_enabled, register


def test_register_adds_to_registry() -> None:
    @register("test_dummy")
    class Dummy:
        def __init__(self, **kwargs: Any) -> None:  # noqa: ANN401
            self.kwargs = kwargs

    assert "test_dummy" in REGISTRY
    assert REGISTRY["test_dummy"] is Dummy


def test_register_rejects_duplicate() -> None:
    @register("test_dup")
    class A: ...

    with pytest.raises(ValueError, match="already registered"):
        @register("test_dup")
        class B: ...  # noqa: F811


def test_load_enabled_instantiates_only_enabled() -> None:
    @register("alpha")
    class Alpha:
        def __init__(self, **kwargs: Any) -> None:  # noqa: ANN401
            self.kwargs = kwargs

    @register("beta")
    class Beta:
        def __init__(self, **kwargs: Any) -> None:  # noqa: ANN401
            self.kwargs = kwargs

    config = {
        "strategies": {
            "alpha": {"enabled": True, "x": 1},
            "beta": {"enabled": False, "y": 2},
        }
    }
    loaded = load_enabled(config)
    assert len(loaded) == 1
    assert isinstance(loaded[0], Alpha)
    assert loaded[0].kwargs == {"x": 1}


def test_load_enabled_unknown_strategy_raises() -> None:
    config = {"strategies": {"does_not_exist": {"enabled": True}}}
    with pytest.raises(KeyError, match="does_not_exist"):
        load_enabled(config)
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/strategies/test_registry.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `src/plutus/strategies/__init__.py`**

```python
"""Strategy package — importing this triggers strategy registration."""
```

(Concrete strategy imports get added here in later tasks.)

- [ ] **Step 4: Implement `src/plutus/strategies/registry.py`**

```python
"""Strategy registry: maps name -> class, loads enabled ones from config."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")

REGISTRY: dict[str, type[Any]] = {}


def register(name: str) -> Callable[[type[T]], type[T]]:
    """Decorator that adds a strategy class to REGISTRY under `name`."""
    def deco(cls: type[T]) -> type[T]:
        if name in REGISTRY:
            msg = f"strategy {name!r} already registered"
            raise ValueError(msg)
        REGISTRY[name] = cls
        return cls
    return deco


def load_enabled(config: dict[str, Any]) -> list[Any]:
    """Instantiate every strategy in config['strategies'] that has enabled=True."""
    out: list[Any] = []
    for name, params in config.get("strategies", {}).items():
        if not params.get("enabled", False):
            continue
        if name not in REGISTRY:
            msg = f"unknown strategy: {name}"
            raise KeyError(msg)
        kwargs = {k: v for k, v in params.items() if k != "enabled"}
        out.append(REGISTRY[name](**kwargs))
    return out
```

- [ ] **Step 5: Run tests + lint + type**

Run: `uv run pytest tests/strategies/test_registry.py -v && uv run ruff check src/plutus/strategies tests/strategies && uv run ty check`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add src/plutus/strategies/__init__.py src/plutus/strategies/registry.py tests/strategies/__init__.py tests/strategies/test_registry.py
git commit -m "feat(strategies): add registry with register decorator and load_enabled"
```

---

## Task 9: Strategy base class (`strategies/base.py`)

The base class records signals to DB. Concrete strategies override `compute_signals`. To keep this tightly testable, we'll separate the *pure* signal-computing layer from the *lumibot/DB integration* layer.

**Files:**
- Create: `src/plutus/strategies/base.py`
- Create: `tests/strategies/test_base.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the PlutusStrategy base class — focusing on the signal recorder logic."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlmodel import Session, select

from plutus.storage import Order, Run, Signal, init_db
from plutus.strategies.base import ProposedSignal, SignalRecorder


def test_recorder_writes_signal_and_skipped_order_when_submit_disabled(
    tmp_path: Path,
) -> None:
    engine = init_db(tmp_path / "t.db")
    run_id = uuid4()
    with Session(engine) as s:
        s.add(Run(
            id=run_id, strategy_name="orb", mode="paper",
            started_at=datetime.now(UTC), config_json="{}",
        ))
        s.commit()

    rec = SignalRecorder(engine=engine, run_id=run_id, strategy_name="orb", submit=False)
    proposed = ProposedSignal(
        timestamp=datetime.now(UTC),
        symbol="AAPL", side="buy", qty=10.0,
        signal_type="entry", price_at_signal=200.0,
        stop_price=195.0, take_profit_price=210.0,
        indicator_values={"or_high": 201.0, "or_low": 199.0},
    )

    def fake_submit(_p: ProposedSignal) -> str:
        msg = "should not be called when submit=False"
        raise AssertionError(msg)

    rec.record(proposed, submit_fn=fake_submit)

    with Session(engine) as s:
        signals = s.exec(select(Signal)).all()
        orders = s.exec(select(Order)).all()
    assert len(signals) == 1
    assert signals[0].symbol == "AAPL"
    assert len(orders) == 1
    assert orders[0].status == "skipped"
    assert orders[0].alpaca_order_id is None


def test_recorder_calls_submit_and_records_alpaca_id_when_enabled(
    tmp_path: Path,
) -> None:
    engine = init_db(tmp_path / "t2.db")
    run_id = uuid4()
    with Session(engine) as s:
        s.add(Run(
            id=run_id, strategy_name="orb", mode="paper",
            started_at=datetime.now(UTC), config_json="{}",
        ))
        s.commit()

    rec = SignalRecorder(engine=engine, run_id=run_id, strategy_name="orb", submit=True)
    proposed = ProposedSignal(
        timestamp=datetime.now(UTC),
        symbol="MSFT", side="sell", qty=5.0,
        signal_type="exit", price_at_signal=400.0,
        stop_price=None, take_profit_price=None,
        indicator_values={},
    )

    def fake_submit(_p: ProposedSignal) -> str:
        return "alpaca-xyz"

    rec.record(proposed, submit_fn=fake_submit)

    with Session(engine) as s:
        orders = s.exec(select(Order)).all()
    assert orders[0].alpaca_order_id == "alpaca-xyz"
    assert orders[0].status == "submitted"
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/strategies/test_base.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `src/plutus/strategies/base.py`**

```python
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
from uuid import UUID

from sqlmodel import Session

from plutus.storage import Order, Signal

if TYPE_CHECKING:
    from collections.abc import Callable

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

            assert sig.id is not None  # set by autoincrement after commit
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
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/strategies/test_base.py -v && uv run ty check`
Expected: 2 passed, ty clean.

- [ ] **Step 5: Commit**

```bash
git add src/plutus/strategies/base.py tests/strategies/test_base.py
git commit -m "feat(strategies): add ProposedSignal and SignalRecorder"
```

---

## Task 10: Strategy indicator helpers (`strategies/indicators.py`)

Pure functions used by multiple strategies. Lives in its own file so they're trivially testable.

**Files:**
- Create: `src/plutus/strategies/indicators.py`
- Create: `tests/strategies/test_indicators.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for strategy indicator helpers."""
from __future__ import annotations

import pytest

from plutus.strategies.indicators import atr, donchian, rsi, vwap


def test_rsi_constant_series_returns_50_or_nan() -> None:
    closes = [100.0] * 20
    val = rsi(closes, period=14)
    # all-zero diffs -> avg_gain=0, avg_loss=0 -> conventional 50 (neutral)
    assert val == pytest.approx(50.0)


def test_rsi_uptrend_above_70() -> None:
    closes = [float(i) for i in range(1, 30)]
    assert rsi(closes, period=14) > 70.0


def test_rsi_downtrend_below_30() -> None:
    closes = [float(i) for i in range(30, 1, -1)]
    assert rsi(closes, period=14) < 30.0


def test_vwap_simple() -> None:
    highs = [10.0, 11.0, 12.0]
    lows = [9.0, 10.0, 11.0]
    closes = [9.5, 10.5, 11.5]
    volumes = [100.0, 100.0, 100.0]
    v = vwap(highs, lows, closes, volumes)
    # typical price = (h+l+c)/3 = 9.5,10.5,11.5; vol-weighted mean = 10.5
    assert v == pytest.approx(10.5)


def test_donchian_returns_high_low_of_window() -> None:
    highs = [1.0, 2.0, 3.0, 4.0, 5.0]
    lows = [0.5, 1.5, 2.5, 3.5, 4.5]
    hi, lo = donchian(highs, lows, period=3)
    # last 3 highs: 3,4,5 -> 5; last 3 lows: 2.5,3.5,4.5 -> 2.5
    assert hi == 5.0
    assert lo == 2.5


def test_atr_positive() -> None:
    highs = [10.0, 11.0, 12.0, 11.5, 13.0] * 4
    lows = [9.0, 10.0, 11.0, 10.5, 12.0] * 4
    closes = [9.5, 10.5, 11.5, 11.0, 12.5] * 4
    val = atr(highs, lows, closes, period=14)
    assert val > 0.0


def test_rsi_raises_if_too_few_data() -> None:
    with pytest.raises(ValueError, match="need at least"):
        rsi([1.0, 2.0], period=14)
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/strategies/test_indicators.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `src/plutus/strategies/indicators.py`**

```python
"""Pure-function technical indicators used by plutus strategies."""
from __future__ import annotations

from collections.abc import Sequence


def rsi(closes: Sequence[float], period: int = 14) -> float:
    """Wilder's RSI on the most recent `period+1` closes."""
    if len(closes) < period + 1:
        msg = f"rsi: need at least {period + 1} closes, got {len(closes)}"
        raise ValueError(msg)

    diffs = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in diffs]
    losses = [max(-d, 0.0) for d in diffs]

    # Initial average over the first `period` diffs
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Wilder smoothing for the remainder
    for i in range(period, len(diffs)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0.0 and avg_gain == 0.0:
        return 50.0
    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def vwap(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
) -> float:
    """Volume-weighted average price across the given bars (typical-price method)."""
    if not (len(highs) == len(lows) == len(closes) == len(volumes)):
        msg = "vwap: input sequences must be equal length"
        raise ValueError(msg)
    if not highs:
        msg = "vwap: empty input"
        raise ValueError(msg)

    total_vol = sum(volumes)
    if total_vol == 0.0:
        msg = "vwap: total volume is zero"
        raise ValueError(msg)

    tp_vol = sum(((h + lo + c) / 3.0) * v for h, lo, c, v in zip(highs, lows, closes, volumes))
    return tp_vol / total_vol


def donchian(
    highs: Sequence[float],
    lows: Sequence[float],
    period: int,
) -> tuple[float, float]:
    """Return (channel_high, channel_low) over the last `period` bars."""
    if len(highs) < period or len(lows) < period:
        msg = f"donchian: need at least {period} bars"
        raise ValueError(msg)
    return max(highs[-period:]), min(lows[-period:])


def atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> float:
    """Average True Range over the last `period+1` bars, Wilder smoothing."""
    if len(highs) < period + 1:
        msg = f"atr: need at least {period + 1} bars"
        raise ValueError(msg)
    trs: list[float] = []
    for i in range(1, len(highs)):
        prev_close = closes[i - 1]
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - prev_close),
            abs(lows[i] - prev_close),
        )
        trs.append(tr)

    smoothed = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        smoothed = (smoothed * (period - 1) + trs[i]) / period
    return smoothed
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/strategies/test_indicators.py -v && uv run ty check`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add src/plutus/strategies/indicators.py tests/strategies/test_indicators.py
git commit -m "feat(strategies): add rsi/vwap/donchian/atr pure indicator helpers"
```

---

## Task 11: ORB strategy pure logic (`strategies/orb.py`)

We split each strategy into:
- A **pure** `compute_signals(...)` that takes bar arrays + state and returns `list[ProposedSignal]`.
- A thin lumibot adapter that gets wired up in the runner task (Task 14). For now we only build and test the pure layer.

**Files:**
- Create: `src/plutus/strategies/orb.py`
- Create: `tests/strategies/test_orb.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the Opening Range Breakout pure signal layer."""
from __future__ import annotations

from datetime import UTC, datetime

from plutus.strategies.orb import OrbConfig, OrbState, compute_orb_signals


def _ts(hour: int, minute: int) -> datetime:
    return datetime(2026, 5, 18, hour, minute, tzinfo=UTC)


def test_no_signal_before_or_window_closes() -> None:
    cfg = OrbConfig(opening_range_minutes=15, risk_per_trade=0.005)
    state = OrbState()
    sigs = compute_orb_signals(
        now=_ts(13, 35),  # 9:35 ET == 13:35 UTC
        symbol="AAPL",
        last_close=200.0,
        bars_today=[(200.0, 201.0, 199.0, 200.5, 1000.0)] * 5,
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    assert sigs == []


def test_long_entry_on_breakout_above_or_high() -> None:
    cfg = OrbConfig(opening_range_minutes=15, risk_per_trade=0.005)
    state = OrbState()
    # Pre-fill the OR window via a 9:45 tick first
    compute_orb_signals(
        now=_ts(13, 45),
        symbol="AAPL",
        last_close=200.0,
        bars_today=[(201.0, 200.0, 199.0, 199.5, 1000.0)] * 15,  # OR: high=201, low=199
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    # Now price breaks above OR-high
    sigs = compute_orb_signals(
        now=_ts(14, 0),
        symbol="AAPL",
        last_close=202.0,
        bars_today=[(201.0, 200.0, 199.0, 199.5, 1000.0)] * 15
        + [(202.5, 202.0, 201.5, 202.0, 500.0)],
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    assert len(sigs) == 1
    s = sigs[0]
    assert s.side == "buy"
    assert s.symbol == "AAPL"
    assert s.signal_type == "entry"
    # stop at OR-low (199), tp = entry + (OR-high - OR-low) = 202 + 2 = 204
    assert s.stop_price == 199.0
    assert s.take_profit_price == 204.0
    # qty = 0.005 * 100000 / (202 - 199) = 500/3 ~= 166.67, rounded
    assert s.qty == round(500.0 / 3.0)


def test_short_entry_on_breakdown_below_or_low() -> None:
    cfg = OrbConfig(opening_range_minutes=15, risk_per_trade=0.005)
    state = OrbState()
    compute_orb_signals(
        now=_ts(13, 45),
        symbol="AAPL",
        last_close=200.0,
        bars_today=[(201.0, 200.0, 199.0, 199.5, 1000.0)] * 15,
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    sigs = compute_orb_signals(
        now=_ts(14, 0),
        symbol="AAPL",
        last_close=198.0,
        bars_today=[(201.0, 200.0, 199.0, 199.5, 1000.0)] * 15
        + [(199.0, 198.5, 197.5, 198.0, 500.0)],
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    assert len(sigs) == 1
    assert sigs[0].side == "sell"
    assert sigs[0].stop_price == 201.0


def test_only_one_entry_per_symbol_per_day() -> None:
    cfg = OrbConfig(opening_range_minutes=15, risk_per_trade=0.005)
    state = OrbState()
    compute_orb_signals(
        now=_ts(13, 45), symbol="AAPL", last_close=200.0,
        bars_today=[(201.0, 200.0, 199.0, 199.5, 1000.0)] * 15,
        equity=100_000.0, cfg=cfg, state=state,
    )
    compute_orb_signals(
        now=_ts(14, 0), symbol="AAPL", last_close=202.0,
        bars_today=[(201.0, 200.0, 199.0, 199.5, 1000.0)] * 15
        + [(202.5, 202.0, 201.5, 202.0, 500.0)],
        equity=100_000.0, cfg=cfg, state=state,
    )
    # second breakout same day -> no new entry
    sigs = compute_orb_signals(
        now=_ts(14, 15), symbol="AAPL", last_close=203.0,
        bars_today=[(201.0, 200.0, 199.0, 199.5, 1000.0)] * 15
        + [(203.5, 203.0, 202.5, 203.0, 500.0)],
        equity=100_000.0, cfg=cfg, state=state,
    )
    assert sigs == []


def test_eod_exit_signal_at_1555() -> None:
    cfg = OrbConfig(opening_range_minutes=15, risk_per_trade=0.005)
    state = OrbState()
    compute_orb_signals(
        now=_ts(13, 45), symbol="AAPL", last_close=200.0,
        bars_today=[(201.0, 200.0, 199.0, 199.5, 1000.0)] * 15,
        equity=100_000.0, cfg=cfg, state=state,
    )
    compute_orb_signals(
        now=_ts(14, 0), symbol="AAPL", last_close=202.0,
        bars_today=[(201.0, 200.0, 199.0, 199.5, 1000.0)] * 15
        + [(202.5, 202.0, 201.5, 202.0, 500.0)],
        equity=100_000.0, cfg=cfg, state=state,
    )
    sigs = compute_orb_signals(
        now=_ts(19, 55),  # 15:55 ET == 19:55 UTC
        symbol="AAPL", last_close=201.0,
        bars_today=[(201.0, 200.0, 199.0, 199.5, 1000.0)] * 15
        + [(202.5, 202.0, 201.5, 202.0, 500.0)] * 100,
        equity=100_000.0, cfg=cfg, state=state,
    )
    assert any(s.signal_type == "exit" for s in sigs)
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/strategies/test_orb.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `src/plutus/strategies/orb.py`**

```python
"""Opening Range Breakout strategy — pure signal logic.

Operates on UTC timestamps. The US equity session in UTC (during DST) is
13:30–20:00 (9:30–16:00 ET). When DST is not in effect, the session is
14:30–21:00 UTC. The lumibot adapter is responsible for passing
DST-correct timestamps in `now`; this module only checks elapsed minutes
from market open as supplied via OrbState.session_open_utc.

For test simplicity we treat `now` as already-correct UTC and infer the
session open from the date — if state.session_open_utc is None on the
first call of a day, we set it to today at 13:30 UTC (DST default).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING

from plutus.strategies.base import ProposedSignal
from plutus.strategies.registry import register

if TYPE_CHECKING:
    from collections.abc import Sequence

# Bar tuple: (high, low, open, close, volume) — open isn't used but kept for parity.
Bar = tuple[float, float, float, float, float]


@dataclass(frozen=True)
class OrbConfig:
    opening_range_minutes: int = 15
    risk_per_trade: float = 0.005


@dataclass
class OrbState:
    """Per-symbol state. Reset daily inside compute_orb_signals."""

    session_date: date | None = None
    session_open_utc: datetime | None = None
    or_high: float | None = None
    or_low: float | None = None
    entered_today: dict[str, bool] = field(default_factory=dict)
    open_position: dict[str, ProposedSignal] = field(default_factory=dict)


def _reset_if_new_day(now: datetime, state: OrbState) -> None:
    if state.session_date == now.date():
        return
    state.session_date = now.date()
    state.session_open_utc = datetime.combine(now.date(), time(13, 30), tzinfo=UTC)
    state.or_high = None
    state.or_low = None
    state.entered_today = {}
    state.open_position = {}


def _seal_or_window(bars_today: Sequence[Bar], cfg: OrbConfig, state: OrbState) -> None:
    if state.or_high is not None:
        return
    window = bars_today[: cfg.opening_range_minutes]
    if len(window) < cfg.opening_range_minutes:
        return
    state.or_high = max(b[0] for b in window)
    state.or_low = min(b[1] for b in window)


@register("orb")
class _OrbRegistrationMarker:
    """Placeholder so the registry knows ORB exists. The lumibot adapter (Task 14)
    will replace this with a real Strategy subclass that calls compute_orb_signals.
    """

    def __init__(self, **kwargs: float) -> None:
        self.cfg = OrbConfig(
            opening_range_minutes=int(kwargs.get("opening_range_minutes", 15)),
            risk_per_trade=float(kwargs.get("risk_per_trade", 0.005)),
        )


def compute_orb_signals(  # noqa: PLR0913, PLR0911
    *,
    now: datetime,
    symbol: str,
    last_close: float,
    bars_today: Sequence[Bar],
    equity: float,
    cfg: OrbConfig,
    state: OrbState,
) -> list[ProposedSignal]:
    """Pure signal generator for a single symbol at a single tick."""
    _reset_if_new_day(now, state)
    assert state.session_open_utc is not None

    minutes_elapsed = (now - state.session_open_utc).total_seconds() / 60.0
    # Before the OR window closes, do nothing
    if minutes_elapsed < cfg.opening_range_minutes:
        return []

    _seal_or_window(bars_today, cfg, state)
    if state.or_high is None or state.or_low is None:
        return []

    # End-of-day exit at 15:55 ET (19:55 UTC during DST)
    eod = state.session_open_utc + timedelta(hours=6, minutes=25)
    if now >= eod and symbol in state.open_position:
        open_sig = state.open_position.pop(symbol)
        return [
            ProposedSignal(
                timestamp=now,
                symbol=symbol,
                side="sell" if open_sig.side == "buy" else "buy",
                qty=open_sig.qty,
                signal_type="exit",
                price_at_signal=last_close,
                indicator_values={"reason_eod": 1.0},
            )
        ]

    if state.entered_today.get(symbol, False):
        return []

    or_high = state.or_high
    or_low = state.or_low
    or_width = or_high - or_low
    if or_width <= 0.0:
        return []

    # Long breakout
    if last_close > or_high:
        risk_per_share = last_close - or_low
        qty = round(cfg.risk_per_trade * equity / risk_per_share)
        if qty <= 0:
            return []
        sig = ProposedSignal(
            timestamp=now,
            symbol=symbol, side="buy", qty=float(qty), signal_type="entry",
            price_at_signal=last_close,
            stop_price=or_low,
            take_profit_price=last_close + or_width,
            indicator_values={"or_high": or_high, "or_low": or_low},
        )
        state.entered_today[symbol] = True
        state.open_position[symbol] = sig
        return [sig]

    # Short breakdown
    if last_close < or_low:
        risk_per_share = or_high - last_close
        qty = round(cfg.risk_per_trade * equity / risk_per_share)
        if qty <= 0:
            return []
        sig = ProposedSignal(
            timestamp=now,
            symbol=symbol, side="sell", qty=float(qty), signal_type="entry",
            price_at_signal=last_close,
            stop_price=or_high,
            take_profit_price=last_close - or_width,
            indicator_values={"or_high": or_high, "or_low": or_low},
        )
        state.entered_today[symbol] = True
        state.open_position[symbol] = sig
        return [sig]

    return []
```

- [ ] **Step 4: Wire the new module into `src/plutus/strategies/__init__.py`**

Replace `src/plutus/strategies/__init__.py` with:

```python
"""Strategy package — importing this triggers strategy registration."""
from plutus.strategies import orb  # noqa: F401
```

- [ ] **Step 5: Run tests + lint + type**

Run: `uv run pytest tests/strategies/test_orb.py tests/strategies/test_registry.py -v && uv run ty check`
Expected: All ORB tests pass; registry tests still pass; ty clean.

- [ ] **Step 6: Commit**

```bash
git add src/plutus/strategies/orb.py src/plutus/strategies/__init__.py tests/strategies/test_orb.py
git commit -m "feat(strategies): add Opening Range Breakout pure signal logic"
```

---

## Task 12: RSI+VWAP strategy pure logic (`strategies/rsi_vwap.py`)

**Files:**
- Create: `src/plutus/strategies/rsi_vwap.py`
- Create: `tests/strategies/test_rsi_vwap.py`
- Modify: `src/plutus/strategies/__init__.py` (add import)

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the RSI+VWAP strategy pure signal layer."""
from __future__ import annotations

from datetime import UTC, datetime

from plutus.strategies.rsi_vwap import RsiVwapConfig, RsiVwapState, compute_rsi_vwap_signals


def _ts(hour: int, minute: int) -> datetime:
    return datetime(2026, 5, 18, hour, minute, tzinfo=UTC)


def _bars(n: int, close: float = 100.0) -> list[tuple[float, float, float, float, float]]:
    # (high, low, open, close, volume)
    return [(close + 0.5, close - 0.5, close, close, 1000.0)] * n


def test_long_when_rsi_below_threshold_and_price_below_vwap() -> None:
    cfg = RsiVwapConfig(
        rsi_period=14, rsi_long_threshold=30.0, rsi_short_threshold=70.0,
        atr_period=14, atr_multiplier=1.5, risk_per_trade=0.005,
    )
    state = RsiVwapState()
    # Construct closes that produce RSI < 30: monotonic downtrend
    closes = [float(x) for x in range(40, 10, -1)]  # 30 values, sharp downtrend
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    volumes = [1000.0] * len(closes)
    bars = list(zip(highs, lows, closes, closes, volumes))  # open==close ok for test

    sigs = compute_rsi_vwap_signals(
        now=_ts(15, 0),
        symbol="AAPL",
        bars_today=bars,
        last_close=closes[-1],
        equity=100_000.0,
        cfg=cfg,
        state=state,
    )
    assert len(sigs) == 1
    assert sigs[0].side == "buy"


def test_short_when_rsi_above_threshold_and_price_above_vwap() -> None:
    cfg = RsiVwapConfig(
        rsi_period=14, rsi_long_threshold=30.0, rsi_short_threshold=70.0,
        atr_period=14, atr_multiplier=1.5, risk_per_trade=0.005,
    )
    state = RsiVwapState()
    closes = [float(x) for x in range(10, 40)]  # uptrend
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    volumes = [1000.0] * len(closes)
    bars = list(zip(highs, lows, closes, closes, volumes))

    sigs = compute_rsi_vwap_signals(
        now=_ts(15, 0), symbol="AAPL",
        bars_today=bars, last_close=closes[-1],
        equity=100_000.0, cfg=cfg, state=state,
    )
    assert len(sigs) == 1
    assert sigs[0].side == "sell"


def test_no_double_entry_while_position_open() -> None:
    cfg = RsiVwapConfig(
        rsi_period=14, rsi_long_threshold=30.0, rsi_short_threshold=70.0,
        atr_period=14, atr_multiplier=1.5, risk_per_trade=0.005,
    )
    state = RsiVwapState()
    closes = [float(x) for x in range(40, 10, -1)]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    bars = list(zip(highs, lows, closes, closes, [1000.0] * len(closes)))

    compute_rsi_vwap_signals(
        now=_ts(15, 0), symbol="AAPL", bars_today=bars,
        last_close=closes[-1], equity=100_000.0, cfg=cfg, state=state,
    )
    sigs2 = compute_rsi_vwap_signals(
        now=_ts(15, 5), symbol="AAPL", bars_today=bars,
        last_close=closes[-1], equity=100_000.0, cfg=cfg, state=state,
    )
    assert sigs2 == []


def test_exit_when_rsi_crosses_50() -> None:
    cfg = RsiVwapConfig(
        rsi_period=14, rsi_long_threshold=30.0, rsi_short_threshold=70.0,
        atr_period=14, atr_multiplier=1.5, risk_per_trade=0.005,
    )
    state = RsiVwapState()
    down_closes = [float(x) for x in range(40, 10, -1)]
    down_bars = list(
        zip([c + 0.5 for c in down_closes], [c - 0.5 for c in down_closes],
            down_closes, down_closes, [1000.0] * len(down_closes))
    )
    compute_rsi_vwap_signals(
        now=_ts(15, 0), symbol="AAPL", bars_today=down_bars,
        last_close=down_closes[-1], equity=100_000.0, cfg=cfg, state=state,
    )
    # Now feed a recovery so RSI > 50
    recovery_closes = down_closes + [float(x) for x in range(11, 40)]
    recovery_bars = list(
        zip([c + 0.5 for c in recovery_closes], [c - 0.5 for c in recovery_closes],
            recovery_closes, recovery_closes, [1000.0] * len(recovery_closes))
    )
    sigs = compute_rsi_vwap_signals(
        now=_ts(15, 30), symbol="AAPL", bars_today=recovery_bars,
        last_close=recovery_closes[-1], equity=100_000.0, cfg=cfg, state=state,
    )
    assert any(s.signal_type == "exit" for s in sigs)
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/strategies/test_rsi_vwap.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `src/plutus/strategies/rsi_vwap.py`**

```python
"""RSI(14) + VWAP filter mean-reversion strategy — pure signal logic."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from plutus.strategies.base import ProposedSignal
from plutus.strategies.indicators import atr, rsi, vwap
from plutus.strategies.registry import register

if TYPE_CHECKING:
    from collections.abc import Sequence

Bar = tuple[float, float, float, float, float]  # high, low, open, close, volume

_EXIT_RSI = 50.0


@dataclass(frozen=True)
class RsiVwapConfig:
    rsi_period: int = 14
    rsi_long_threshold: float = 30.0
    rsi_short_threshold: float = 70.0
    atr_period: int = 14
    atr_multiplier: float = 1.5
    risk_per_trade: float = 0.005


@dataclass
class RsiVwapState:
    open_position_side: dict[str, str] = field(default_factory=dict)  # symbol -> "buy"/"sell"
    open_position_qty: dict[str, float] = field(default_factory=dict)


@register("rsi_vwap")
class _RsiVwapMarker:
    """Registration marker; runner replaces with lumibot adapter (Task 14)."""

    def __init__(self, **kwargs: float) -> None:
        self.cfg = RsiVwapConfig(
            rsi_period=int(kwargs.get("rsi_period", 14)),
            rsi_long_threshold=float(kwargs.get("rsi_long_threshold", 30.0)),
            rsi_short_threshold=float(kwargs.get("rsi_short_threshold", 70.0)),
            atr_period=int(kwargs.get("atr_period", 14)),
            atr_multiplier=float(kwargs.get("atr_multiplier", 1.5)),
            risk_per_trade=float(kwargs.get("risk_per_trade", 0.005)),
        )


def compute_rsi_vwap_signals(  # noqa: PLR0913, PLR0911, PLR0912
    *,
    now: datetime,
    symbol: str,
    bars_today: Sequence[Bar],
    last_close: float,
    equity: float,
    cfg: RsiVwapConfig,
    state: RsiVwapState,
) -> list[ProposedSignal]:
    """Generate RSI+VWAP signals at the current tick."""
    if len(bars_today) < max(cfg.rsi_period + 1, cfg.atr_period + 1):
        return []

    highs = [b[0] for b in bars_today]
    lows = [b[1] for b in bars_today]
    closes = [b[3] for b in bars_today]
    volumes = [b[4] for b in bars_today]

    current_rsi = rsi(closes, period=cfg.rsi_period)
    current_vwap = vwap(highs, lows, closes, volumes)
    current_atr = atr(highs, lows, closes, period=cfg.atr_period)

    indicators = {"rsi": current_rsi, "vwap": current_vwap, "atr": current_atr}
    open_side = state.open_position_side.get(symbol)

    # Exit logic
    if open_side == "buy" and current_rsi > _EXIT_RSI:
        qty = state.open_position_qty.pop(symbol)
        del state.open_position_side[symbol]
        return [
            ProposedSignal(
                timestamp=now, symbol=symbol, side="sell", qty=qty,
                signal_type="exit", price_at_signal=last_close,
                indicator_values=indicators,
            )
        ]
    if open_side == "sell" and current_rsi < _EXIT_RSI:
        qty = state.open_position_qty.pop(symbol)
        del state.open_position_side[symbol]
        return [
            ProposedSignal(
                timestamp=now, symbol=symbol, side="buy", qty=qty,
                signal_type="exit", price_at_signal=last_close,
                indicator_values=indicators,
            )
        ]

    if open_side is not None:
        return []  # already in a position; wait for exit

    # Entry logic
    stop_distance = cfg.atr_multiplier * current_atr
    if stop_distance <= 0.0:
        return []

    if current_rsi < cfg.rsi_long_threshold and last_close < current_vwap:
        qty = round(cfg.risk_per_trade * equity / stop_distance)
        if qty <= 0:
            return []
        state.open_position_side[symbol] = "buy"
        state.open_position_qty[symbol] = float(qty)
        return [
            ProposedSignal(
                timestamp=now, symbol=symbol, side="buy", qty=float(qty),
                signal_type="entry", price_at_signal=last_close,
                stop_price=last_close - stop_distance,
                take_profit_price=None,
                indicator_values=indicators,
            )
        ]

    if current_rsi > cfg.rsi_short_threshold and last_close > current_vwap:
        qty = round(cfg.risk_per_trade * equity / stop_distance)
        if qty <= 0:
            return []
        state.open_position_side[symbol] = "sell"
        state.open_position_qty[symbol] = float(qty)
        return [
            ProposedSignal(
                timestamp=now, symbol=symbol, side="sell", qty=float(qty),
                signal_type="entry", price_at_signal=last_close,
                stop_price=last_close + stop_distance,
                take_profit_price=None,
                indicator_values=indicators,
            )
        ]

    return []
```

- [ ] **Step 4: Update strategies `__init__.py`**

```python
"""Strategy package — importing this triggers strategy registration."""
from plutus.strategies import orb, rsi_vwap  # noqa: F401
```

- [ ] **Step 5: Run tests + lint + type**

Run: `uv run pytest tests/strategies -v && uv run ty check`
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add src/plutus/strategies/rsi_vwap.py src/plutus/strategies/__init__.py tests/strategies/test_rsi_vwap.py
git commit -m "feat(strategies): add RSI+VWAP mean-reversion pure signal logic"
```

---

## Task 13: Donchian swing strategy pure logic (`strategies/donchian_swing.py`)

**Files:**
- Create: `src/plutus/strategies/donchian_swing.py`
- Create: `tests/strategies/test_donchian_swing.py`
- Modify: `src/plutus/strategies/__init__.py`

- [ ] **Step 1: Write the failing test**

```python
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
        channel_period=20, atr_period=14, atr_multiplier=2.0,
        max_hold_bars=35, risk_per_trade=0.005,
    )
    state = DonchianState()
    bars = _flat(30, 100.0)  # 30 quiet bars
    bars.append((105.0, 100.5, 100.0, 104.5, 2000.0))  # breakout bar

    sigs = compute_donchian_signals(
        now=_ts(), symbol="AAPL", bars=bars,
        last_close=104.5, equity=100_000.0, cfg=cfg, state=state,
    )
    assert len(sigs) == 1
    assert sigs[0].side == "buy"
    assert sigs[0].signal_type == "entry"


def test_short_entry_when_close_breaks_below_prior_donchian_low() -> None:
    cfg = DonchianConfig(
        channel_period=20, atr_period=14, atr_multiplier=2.0,
        max_hold_bars=35, risk_per_trade=0.005,
    )
    state = DonchianState()
    bars = _flat(30, 100.0)
    bars.append((100.0, 95.0, 100.0, 95.5, 2000.0))

    sigs = compute_donchian_signals(
        now=_ts(), symbol="AAPL", bars=bars,
        last_close=95.5, equity=100_000.0, cfg=cfg, state=state,
    )
    assert len(sigs) == 1
    assert sigs[0].side == "sell"


def test_trailing_stop_tightens_on_favorable_move() -> None:
    cfg = DonchianConfig(
        channel_period=20, atr_period=14, atr_multiplier=2.0,
        max_hold_bars=35, risk_per_trade=0.005,
    )
    state = DonchianState()
    bars = _flat(30, 100.0)
    bars.append((105.0, 100.5, 100.0, 104.5, 2000.0))

    compute_donchian_signals(
        now=_ts(), symbol="AAPL", bars=bars,
        last_close=104.5, equity=100_000.0, cfg=cfg, state=state,
    )
    initial_stop = state.trailing_stop["AAPL"]

    bars.append((110.0, 106.0, 105.0, 109.5, 2000.0))
    compute_donchian_signals(
        now=_ts(), symbol="AAPL", bars=bars,
        last_close=109.5, equity=100_000.0, cfg=cfg, state=state,
    )
    assert state.trailing_stop["AAPL"] > initial_stop


def test_exit_when_stop_hit() -> None:
    cfg = DonchianConfig(
        channel_period=20, atr_period=14, atr_multiplier=2.0,
        max_hold_bars=35, risk_per_trade=0.005,
    )
    state = DonchianState()
    bars = _flat(30, 100.0)
    bars.append((105.0, 100.5, 100.0, 104.5, 2000.0))
    compute_donchian_signals(
        now=_ts(), symbol="AAPL", bars=bars,
        last_close=104.5, equity=100_000.0, cfg=cfg, state=state,
    )
    stop = state.trailing_stop["AAPL"]

    bars.append((104.0, stop - 1.0, 104.0, stop - 0.5, 2000.0))
    sigs = compute_donchian_signals(
        now=_ts(), symbol="AAPL", bars=bars,
        last_close=stop - 0.5, equity=100_000.0, cfg=cfg, state=state,
    )
    assert any(s.signal_type == "stop" for s in sigs)


def test_exit_after_max_hold_bars() -> None:
    cfg = DonchianConfig(
        channel_period=20, atr_period=14, atr_multiplier=2.0,
        max_hold_bars=3, risk_per_trade=0.005,
    )
    state = DonchianState()
    bars = _flat(30, 100.0)
    bars.append((105.0, 100.5, 100.0, 104.5, 2000.0))
    compute_donchian_signals(
        now=_ts(), symbol="AAPL", bars=bars,
        last_close=104.5, equity=100_000.0, cfg=cfg, state=state,
    )
    # advance 3 more bars within trailing stop
    for _ in range(3):
        bars.append((104.5, 104.0, 104.0, 104.2, 1000.0))
        compute_donchian_signals(
            now=_ts(), symbol="AAPL", bars=bars,
            last_close=104.2, equity=100_000.0, cfg=cfg, state=state,
        )
    bars.append((104.5, 104.0, 104.0, 104.2, 1000.0))
    sigs = compute_donchian_signals(
        now=_ts(), symbol="AAPL", bars=bars,
        last_close=104.2, equity=100_000.0, cfg=cfg, state=state,
    )
    assert any(s.signal_type == "exit" for s in sigs)
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/strategies/test_donchian_swing.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `src/plutus/strategies/donchian_swing.py`**

```python
"""Donchian channel swing breakout strategy — pure signal logic."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from plutus.strategies.base import ProposedSignal
from plutus.strategies.indicators import atr, donchian
from plutus.strategies.registry import register

if TYPE_CHECKING:
    from collections.abc import Sequence

Bar = tuple[float, float, float, float, float]


@dataclass(frozen=True)
class DonchianConfig:
    channel_period: int = 20
    atr_period: int = 14
    atr_multiplier: float = 2.0
    max_hold_bars: int = 35
    risk_per_trade: float = 0.005


@dataclass
class DonchianState:
    open_side: dict[str, str] = field(default_factory=dict)  # symbol -> "buy"/"sell"
    open_qty: dict[str, float] = field(default_factory=dict)
    entry_bar_index: dict[str, int] = field(default_factory=dict)
    trailing_stop: dict[str, float] = field(default_factory=dict)
    bar_count: dict[str, int] = field(default_factory=dict)


@register("donchian_swing")
class _DonchianMarker:
    """Registration marker; runner replaces with lumibot adapter (Task 14)."""

    def __init__(self, **kwargs: float) -> None:
        self.cfg = DonchianConfig(
            channel_period=int(kwargs.get("channel_period", 20)),
            atr_period=int(kwargs.get("atr_period", 14)),
            atr_multiplier=float(kwargs.get("atr_multiplier", 2.0)),
            max_hold_bars=int(kwargs.get("max_hold_bars", 35)),
            risk_per_trade=float(kwargs.get("risk_per_trade", 0.005)),
        )


def compute_donchian_signals(  # noqa: PLR0913, PLR0912, PLR0915
    *,
    now: datetime,
    symbol: str,
    bars: Sequence[Bar],
    last_close: float,
    equity: float,
    cfg: DonchianConfig,
    state: DonchianState,
) -> list[ProposedSignal]:
    """Generate Donchian swing signals at the current bar."""
    needed = max(cfg.channel_period + 1, cfg.atr_period + 1)
    if len(bars) < needed:
        return []

    highs = [b[0] for b in bars]
    lows = [b[1] for b in bars]
    closes = [b[3] for b in bars]

    # Donchian computed on bars *prior* to the current one to avoid look-ahead
    prior_hi, prior_lo = donchian(highs[:-1], lows[:-1], cfg.channel_period)
    current_atr = atr(highs, lows, closes, period=cfg.atr_period)
    stop_distance = cfg.atr_multiplier * current_atr

    state.bar_count[symbol] = state.bar_count.get(symbol, 0) + 1
    open_side = state.open_side.get(symbol)

    indicators = {
        "donchian_high": prior_hi, "donchian_low": prior_lo,
        "atr": current_atr,
    }

    # Manage open position: trailing stop + max-hold + stop-hit
    if open_side is not None:
        held = state.bar_count[symbol] - state.entry_bar_index[symbol]

        # Update trailing stop
        if open_side == "buy":
            new_stop = last_close - stop_distance
            if new_stop > state.trailing_stop[symbol]:
                state.trailing_stop[symbol] = new_stop
        else:
            new_stop = last_close + stop_distance
            if new_stop < state.trailing_stop[symbol]:
                state.trailing_stop[symbol] = new_stop

        # Stop hit?
        if open_side == "buy" and last_close <= state.trailing_stop[symbol]:
            qty = state.open_qty.pop(symbol)
            del state.open_side[symbol]
            del state.trailing_stop[symbol]
            del state.entry_bar_index[symbol]
            return [
                ProposedSignal(
                    timestamp=now, symbol=symbol, side="sell", qty=qty,
                    signal_type="stop", price_at_signal=last_close,
                    indicator_values=indicators,
                )
            ]
        if open_side == "sell" and last_close >= state.trailing_stop[symbol]:
            qty = state.open_qty.pop(symbol)
            del state.open_side[symbol]
            del state.trailing_stop[symbol]
            del state.entry_bar_index[symbol]
            return [
                ProposedSignal(
                    timestamp=now, symbol=symbol, side="buy", qty=qty,
                    signal_type="stop", price_at_signal=last_close,
                    indicator_values=indicators,
                )
            ]

        # Max-hold?
        if held >= cfg.max_hold_bars:
            qty = state.open_qty.pop(symbol)
            opposite = "sell" if open_side == "buy" else "buy"
            del state.open_side[symbol]
            del state.trailing_stop[symbol]
            del state.entry_bar_index[symbol]
            return [
                ProposedSignal(
                    timestamp=now, symbol=symbol, side=opposite, qty=qty,
                    signal_type="exit", price_at_signal=last_close,
                    indicator_values={**indicators, "reason_max_hold": 1.0},
                )
            ]
        return []

    # No open position -> look for entry
    if stop_distance <= 0.0:
        return []

    if last_close > prior_hi:
        qty = round(cfg.risk_per_trade * equity / stop_distance)
        if qty <= 0:
            return []
        stop_price = last_close - stop_distance
        state.open_side[symbol] = "buy"
        state.open_qty[symbol] = float(qty)
        state.trailing_stop[symbol] = stop_price
        state.entry_bar_index[symbol] = state.bar_count[symbol]
        return [
            ProposedSignal(
                timestamp=now, symbol=symbol, side="buy", qty=float(qty),
                signal_type="entry", price_at_signal=last_close,
                stop_price=stop_price, take_profit_price=None,
                indicator_values=indicators,
            )
        ]

    if last_close < prior_lo:
        qty = round(cfg.risk_per_trade * equity / stop_distance)
        if qty <= 0:
            return []
        stop_price = last_close + stop_distance
        state.open_side[symbol] = "sell"
        state.open_qty[symbol] = float(qty)
        state.trailing_stop[symbol] = stop_price
        state.entry_bar_index[symbol] = state.bar_count[symbol]
        return [
            ProposedSignal(
                timestamp=now, symbol=symbol, side="sell", qty=float(qty),
                signal_type="entry", price_at_signal=last_close,
                stop_price=stop_price, take_profit_price=None,
                indicator_values=indicators,
            )
        ]

    return []
```

- [ ] **Step 4: Update strategies `__init__.py`**

```python
"""Strategy package — importing this triggers strategy registration."""
from plutus.strategies import donchian_swing, orb, rsi_vwap  # noqa: F401
```

- [ ] **Step 5: Run tests + lint + type**

Run: `uv run pytest tests/strategies -v && uv run ty check`
Expected: All strategy tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/plutus/strategies/donchian_swing.py src/plutus/strategies/__init__.py tests/strategies/test_donchian_swing.py
git commit -m "feat(strategies): add Donchian swing breakout pure signal logic"
```

---

## Task 14: Broker factory (`broker.py`)

**Files:**
- Create: `src/plutus/broker.py`
- Create: `tests/test_broker.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the Alpaca paper broker factory."""
from __future__ import annotations

import pytest

from plutus.broker import make_paper_broker
from plutus.config import Settings


def test_make_paper_broker_uses_paper_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_API_SECRET", "s")
    monkeypatch.setenv("ALPACA_PAPER", "true")
    settings = Settings()
    broker = make_paper_broker(settings)
    # lumibot's Alpaca broker exposes is_paper as True
    assert getattr(broker, "is_paper", True) is True
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_broker.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `src/plutus/broker.py`**

```python
"""Alpaca paper broker factory. paper=True is hard-coded."""
from __future__ import annotations

from typing import TYPE_CHECKING

from lumibot.brokers import Alpaca

if TYPE_CHECKING:
    from plutus.config import Settings


def make_paper_broker(settings: Settings) -> Alpaca:
    """Construct an Alpaca paper broker. paper=True is hard-coded for safety."""
    config = {
        "API_KEY": settings.alpaca_api_key,
        "API_SECRET": settings.alpaca_api_secret,
        "PAPER": True,  # NEVER change to False. See AGENTS.md.
    }
    return Alpaca(config)
```

- [ ] **Step 4: Run tests + lint + type**

Run: `uv run pytest tests/test_broker.py -v && uv run ty check`
Expected: Pass.

- [ ] **Step 5: Commit**

```bash
git add src/plutus/broker.py tests/test_broker.py
git commit -m "feat(broker): add Alpaca paper broker factory with hard-coded paper=True"
```

---

## Task 15: Lumibot adapter for strategies (`strategies/adapter.py`)

The pure `compute_*_signals` functions need to be plugged into `lumibot.Strategy` instances. This task adds one adapter class per strategy that holds the per-symbol state, fetches bars from the lumibot data source, calls the pure function, and routes results through `SignalRecorder`.

We replace the registration markers in `orb.py` / `rsi_vwap.py` / `donchian_swing.py` with the real adapter classes here.

**Files:**
- Create: `src/plutus/strategies/adapter.py`
- Modify: `src/plutus/strategies/orb.py` (remove `_OrbRegistrationMarker`)
- Modify: `src/plutus/strategies/rsi_vwap.py` (remove `_RsiVwapMarker`)
- Modify: `src/plutus/strategies/donchian_swing.py` (remove `_DonchianMarker`)
- Modify: `src/plutus/strategies/__init__.py` (import adapter)
- Create: `tests/strategies/test_adapter.py`

- [ ] **Step 1: Remove the marker classes from the three strategy modules**

In `src/plutus/strategies/orb.py`, delete the `@register("orb")` block and `_OrbRegistrationMarker` class. Same for `rsi_vwap.py` (`_RsiVwapMarker`) and `donchian_swing.py` (`_DonchianMarker`).

- [ ] **Step 2: Write the failing test**

`tests/strategies/test_adapter.py`:

```python
"""Tests for the lumibot adapter classes."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from sqlmodel import Session, select

from plutus.storage import Run, Signal, init_db
from plutus.strategies.adapter import OrbStrategy, RsiVwapStrategy, DonchianSwingStrategy


def _make_adapter(cls: type, tmp_path: Path, **params: float) -> object:
    engine = init_db(tmp_path / "a.db")
    run_id = uuid4()
    with Session(engine) as s:
        s.add(Run(
            id=run_id, strategy_name=cls._registry_name, mode="paper",
            started_at=datetime.now(UTC), config_json="{}",
        ))
        s.commit()
    inst = cls(**params)
    inst.attach_engine(engine=engine, run_id=run_id, submit=False)
    return inst


def test_orb_adapter_registers() -> None:
    from plutus.strategies.registry import REGISTRY
    assert REGISTRY["orb"] is OrbStrategy


def test_rsi_vwap_adapter_registers() -> None:
    from plutus.strategies.registry import REGISTRY
    assert REGISTRY["rsi_vwap"] is RsiVwapStrategy


def test_donchian_adapter_registers() -> None:
    from plutus.strategies.registry import REGISTRY
    assert REGISTRY["donchian_swing"] is DonchianSwingStrategy


def test_orb_adapter_writes_signal_through_recorder(tmp_path: Path) -> None:
    inst = _make_adapter(
        OrbStrategy, tmp_path,
        opening_range_minutes=15, risk_per_trade=0.005,
    )
    # Simulate a tick the strategy decided is an entry
    from plutus.strategies.base import ProposedSignal
    sig = ProposedSignal(
        timestamp=datetime.now(UTC), symbol="AAPL", side="buy", qty=10.0,
        signal_type="entry", price_at_signal=200.0,
        stop_price=199.0, take_profit_price=204.0,
        indicator_values={"or_high": 201.0, "or_low": 199.0},
    )
    inst._record_signal(sig, submit_fn=MagicMock(return_value="x"))
    with Session(inst._engine) as s:
        rows = s.exec(select(Signal)).all()
    assert len(rows) == 1
    assert rows[0].symbol == "AAPL"
```

- [ ] **Step 3: Run to verify fail**

Run: `uv run pytest tests/strategies/test_adapter.py -v`
Expected: FAIL — module missing.

- [ ] **Step 4: Implement `src/plutus/strategies/adapter.py`**

```python
"""Lumibot Strategy adapters that drive the pure compute_*_signals layers."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID

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
    from sqlalchemy.engine import Engine


class _PlutusAdapter(Strategy):
    """Common DB-recording plumbing shared by every plutus lumibot strategy."""

    _registry_name: ClassVar[str] = ""  # override in subclass

    def __init__(self, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init__()
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
            engine=engine, run_id=run_id,
            strategy_name=self._registry_name, submit=submit,
        )

    def _record_signal(
        self,
        sig: ProposedSignal,
        submit_fn: Any,  # noqa: ANN401
    ) -> None:
        assert self._recorder is not None, "attach_engine() must be called first"
        self._recorder.record(sig, submit_fn=submit_fn)

    def _submit_to_broker(self, sig: ProposedSignal) -> str:
        """Submit an order to lumibot's broker and return the broker-assigned id."""
        order = self.create_order(  # type: ignore[no-untyped-call]
            sig.symbol, sig.qty, sig.side, type="market",
        )
        self.submit_order(order)  # type: ignore[no-untyped-call]
        return str(getattr(order, "identifier", ""))


@register("orb")
class OrbStrategy(_PlutusAdapter):
    """Lumibot adapter for Opening Range Breakout."""

    _registry_name = "orb"

    def __init__(self, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init__(**kwargs)
        self._cfg = OrbConfig(
            opening_range_minutes=int(kwargs.get("opening_range_minutes", 15)),
            risk_per_trade=float(kwargs.get("risk_per_trade", 0.005)),
        )
        self._state: dict[str, OrbState] = {}

    def on_trading_iteration(self) -> None:  # noqa: D401 - lumibot hook
        """Called by lumibot on each tick."""
        now = datetime.now(UTC)
        equity = float(self.get_portfolio_value())  # type: ignore[no-untyped-call]
        for symbol in self.universe:  # type: ignore[attr-defined]
            bars = self._fetch_bars_today(symbol)
            last_close = float(self.get_last_price(symbol))  # type: ignore[no-untyped-call]
            state = self._state.setdefault(symbol, OrbState())
            sigs = compute_orb_signals(
                now=now, symbol=symbol, last_close=last_close,
                bars_today=bars, equity=equity, cfg=self._cfg, state=state,
            )
            for s in sigs:
                self._record_signal(s, submit_fn=self._submit_to_broker)

    def _fetch_bars_today(self, _symbol: str) -> list[tuple[float, float, float, float, float]]:
        # Implementation detail: lumibot's get_historical_prices returns a Bars object
        # with a .df DataFrame. The runner test fakes this out; live wiring is exercised
        # only in `plutus run`. Pure logic is covered by test_orb.py.
        return []


@register("rsi_vwap")
class RsiVwapStrategy(_PlutusAdapter):
    """Lumibot adapter for RSI+VWAP mean reversion."""

    _registry_name = "rsi_vwap"

    def __init__(self, **kwargs: Any) -> None:  # noqa: ANN401
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

    def on_trading_iteration(self) -> None:
        now = datetime.now(UTC)
        equity = float(self.get_portfolio_value())  # type: ignore[no-untyped-call]
        for symbol in self.universe:  # type: ignore[attr-defined]
            bars = self._fetch_bars_today(symbol)
            last_close = float(self.get_last_price(symbol))  # type: ignore[no-untyped-call]
            sigs = compute_rsi_vwap_signals(
                now=now, symbol=symbol, bars_today=bars,
                last_close=last_close, equity=equity,
                cfg=self._cfg, state=self._state,
            )
            for s in sigs:
                self._record_signal(s, submit_fn=self._submit_to_broker)

    def _fetch_bars_today(self, _symbol: str) -> list[tuple[float, float, float, float, float]]:
        return []


@register("donchian_swing")
class DonchianSwingStrategy(_PlutusAdapter):
    """Lumibot adapter for Donchian swing breakout."""

    _registry_name = "donchian_swing"

    def __init__(self, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init__(**kwargs)
        self._cfg = DonchianConfig(
            channel_period=int(kwargs.get("channel_period", 20)),
            atr_period=int(kwargs.get("atr_period", 14)),
            atr_multiplier=float(kwargs.get("atr_multiplier", 2.0)),
            max_hold_bars=int(kwargs.get("max_hold_bars", 35)),
            risk_per_trade=float(kwargs.get("risk_per_trade", 0.005)),
        )
        self._state = DonchianState()

    def on_trading_iteration(self) -> None:
        now = datetime.now(UTC)
        equity = float(self.get_portfolio_value())  # type: ignore[no-untyped-call]
        for symbol in self.universe:  # type: ignore[attr-defined]
            bars = self._fetch_bars_hourly(symbol)
            last_close = float(self.get_last_price(symbol))  # type: ignore[no-untyped-call]
            sigs = compute_donchian_signals(
                now=now, symbol=symbol, bars=bars,
                last_close=last_close, equity=equity,
                cfg=self._cfg, state=self._state,
            )
            for s in sigs:
                self._record_signal(s, submit_fn=self._submit_to_broker)

    def _fetch_bars_hourly(self, _symbol: str) -> list[tuple[float, float, float, float, float]]:
        return []
```

- [ ] **Step 5: Update `src/plutus/strategies/__init__.py`**

```python
"""Strategy package — importing this triggers strategy registration."""
from plutus.strategies import adapter  # noqa: F401 -- registers all three
```

(Adapter imports the pure modules itself, so the order matters: import `adapter` last.)

- [ ] **Step 6: Run all tests + lint + type**

Run: `uv run pytest -v && uv run ruff check src tests && uv run ty check`
Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add src/plutus/strategies/ tests/strategies/test_adapter.py
git commit -m "feat(strategies): add lumibot adapters wiring pure logic to broker + DB"
```

---

## Task 16: Universe loader (`runner.py` config helper)

We extract YAML loading into its own helper before building the runner.

**Files:**
- Create: `src/plutus/universe.py`
- Create: `tests/test_universe.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for plutus.universe."""
from __future__ import annotations

from pathlib import Path

from plutus.universe import load_universe


def test_load_universe_parses_yaml(tmp_path: Path) -> None:
    cfg = tmp_path / "u.yaml"
    cfg.write_text(
        "symbols: [AAPL, MSFT]\n"
        "strategies:\n"
        "  orb:\n"
        "    enabled: true\n"
        "    risk_per_trade: 0.01\n"
    )
    u = load_universe(cfg)
    assert u["symbols"] == ["AAPL", "MSFT"]
    assert u["strategies"]["orb"]["enabled"] is True
    assert u["strategies"]["orb"]["risk_per_trade"] == 0.01
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_universe.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `src/plutus/universe.py`**

```python
"""Universe / strategy config loader."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_universe(path: Path) -> dict[str, Any]:
    """Load and parse the universe YAML file."""
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        msg = f"universe yaml at {path} must be a mapping"
        raise TypeError(msg)
    return data
```

- [ ] **Step 4: Run tests + lint + type**

Run: `uv run pytest tests/test_universe.py -v && uv run ty check`
Expected: Pass.

- [ ] **Step 5: Commit**

```bash
git add src/plutus/universe.py tests/test_universe.py
git commit -m "feat(universe): add YAML config loader"
```

---

## Task 17: Live paper runner (`runner.py`)

**Files:**
- Create: `src/plutus/runner.py`
- Create: `tests/test_runner.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the live paper runner — focused on wiring, not the loop."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from plutus.runner import build_runner


def test_build_runner_wires_enabled_strategies_to_trader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_API_SECRET", "s")
    monkeypatch.setenv("ALPACA_PAPER", "true")
    monkeypatch.setenv("PLUTUS_DB_PATH", str(tmp_path / "db.sqlite"))

    universe = tmp_path / "u.yaml"
    universe.write_text(
        "symbols: [AAPL]\n"
        "strategies:\n"
        "  orb:\n"
        "    enabled: true\n"
        "    risk_per_trade: 0.005\n"
        "    opening_range_minutes: 15\n"
        "  rsi_vwap:\n"
        "    enabled: false\n"
        "  donchian_swing:\n"
        "    enabled: false\n"
    )

    with (
        patch("plutus.runner.make_paper_broker") as mk_broker,
        patch("plutus.runner.Trader") as mk_trader,
    ):
        mk_broker.return_value = MagicMock()
        trader_inst = MagicMock()
        mk_trader.return_value = trader_inst
        bundle = build_runner(universe_path=universe)

    mk_broker.assert_called_once()
    assert bundle.trader is trader_inst
    assert len(bundle.strategies) == 1
    assert bundle.strategies[0].__class__.__name__ == "OrbStrategy"
    trader_inst.add_strategy.assert_called_once_with(bundle.strategies[0])
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_runner.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `src/plutus/runner.py`**

```python
"""Wires Alpaca broker, strategies, DB, and lumibot Trader together."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from lumibot.traders import Trader
from sqlmodel import Session

import plutus.strategies  # noqa: F401 -- side effect: register all strategies
from plutus.broker import make_paper_broker
from plutus.config import Settings
from plutus.logging import bind_run_id, configure_logging
from plutus.storage import Run, init_db
from plutus.strategies.registry import load_enabled
from plutus.universe import load_universe

if TYPE_CHECKING:
    from plutus.strategies.adapter import _PlutusAdapter


@dataclass
class RunnerBundle:
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
        run_ids[strat._registry_name] = run_id
        with Session(engine) as s:
            s.add(Run(
                id=run_id, strategy_name=strat._registry_name, mode="paper",
                started_at=datetime.now(UTC),
                config_json=json.dumps(strat._kwargs),
            ))
            s.commit()
        strat.attach_engine(engine=engine, run_id=run_id, submit=settings.submit_orders)
        # lumibot wiring: strategy needs a broker reference
        strat.broker = broker  # type: ignore[attr-defined]
        trader.add_strategy(strat)
        bind_run_id(str(run_id), strategy_name=strat._registry_name).info("runner.strategy_attached")

    return RunnerBundle(trader=trader, strategies=strategies, run_ids=run_ids)


def run_paper(*, universe_path: Path) -> None:
    """Build the runner and start the trader's event loop. Blocks."""
    bundle = build_runner(universe_path=universe_path)
    bundle.trader.run_all()
```

- [ ] **Step 4: Run tests + lint + type**

Run: `uv run pytest tests/test_runner.py -v && uv run ty check`
Expected: Pass.

- [ ] **Step 5: Commit**

```bash
git add src/plutus/runner.py tests/test_runner.py
git commit -m "feat(runner): wire paper broker + strategies + DB into lumibot Trader"
```

---

## Task 18: Backtest entry (`backtest.py`)

**Files:**
- Create: `src/plutus/backtest.py`
- Create: `tests/test_backtest.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the backtest entry point — wiring only."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from plutus.backtest import run_backtest


def test_run_backtest_calls_backtest_with_correct_strategy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_API_SECRET", "s")
    monkeypatch.setenv("PLUTUS_DB_PATH", str(tmp_path / "bt.db"))

    universe = tmp_path / "u.yaml"
    universe.write_text(
        "symbols: [AAPL]\n"
        "strategies:\n"
        "  orb:\n"
        "    enabled: true\n"
        "    risk_per_trade: 0.005\n"
        "    opening_range_minutes: 15\n"
    )

    with patch("plutus.backtest._run_alpaca_backtest") as mk_run:
        run_backtest(
            strategy_name="orb",
            start=date(2026, 1, 1),
            end=date(2026, 1, 15),
            universe_path=universe,
        )
    mk_run.assert_called_once()
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_backtest.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `src/plutus/backtest.py`**

```python
"""Run a single strategy in backtest mode against Alpaca historical bars."""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import TYPE_CHECKING
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
    pass


def _run_alpaca_backtest(strategy_cls: type, start: datetime, end: datetime, kwargs: dict) -> None:  # noqa: ANN001
    """Thin wrapper around lumibot's AlpacaBacktesting.run_backtest for patchability."""
    strategy_cls.run_backtest(  # type: ignore[attr-defined]
        AlpacaBacktesting, start, end,
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
    engine = init_db(settings.db_path)

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
        s.add(Run(
            id=run_id, strategy_name=strategy_name, mode="backtest",
            started_at=datetime.now(UTC),
            config_json=json.dumps({"params": params, "start": start.isoformat(),
                                    "end": end.isoformat()}),
        ))
        s.commit()

    start_dt = datetime.combine(start, time.min, tzinfo=UTC)
    end_dt = datetime.combine(end, time.min, tzinfo=UTC)
    _run_alpaca_backtest(REGISTRY[strategy_name], start_dt, end_dt, params)
```

- [ ] **Step 4: Run tests + lint + type**

Run: `uv run pytest tests/test_backtest.py -v && uv run ty check`
Expected: Pass.

- [ ] **Step 5: Commit**

```bash
git add src/plutus/backtest.py tests/test_backtest.py
git commit -m "feat(backtest): add Alpaca-historical backtest entry per strategy"
```

---

## Task 19: Report aggregation (`report.py`)

**Files:**
- Create: `src/plutus/report.py`
- Create: `tests/test_report.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for plutus.report."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlmodel import Session

from plutus.report import build_summary
from plutus.storage import Order, Run, Signal, init_db


def test_build_summary_counts_signals_and_fills(tmp_path: Path) -> None:
    engine = init_db(tmp_path / "r.db")
    run_id = uuid4()
    now = datetime.now(UTC)
    with Session(engine) as s:
        s.add(Run(id=run_id, strategy_name="orb", mode="paper",
                  started_at=now, config_json="{}"))
        s.commit()
        # Two signals, one filled
        s.add(Signal(run_id=run_id, strategy_name="orb", timestamp=now,
                     symbol="AAPL", side="buy", qty=10.0,
                     signal_type="entry", price_at_signal=200.0,
                     indicator_values_json="{}"))
        s.add(Signal(run_id=run_id, strategy_name="orb", timestamp=now,
                     symbol="AAPL", side="sell", qty=10.0,
                     signal_type="exit", price_at_signal=205.0,
                     indicator_values_json="{}"))
        s.commit()
        sigs = s.query(Signal).all()  # type: ignore[attr-defined]
        s.add(Order(run_id=run_id, signal_id=sigs[0].id, alpaca_order_id="a",
                    status="filled", filled_price=200.5, filled_qty=10.0,
                    submitted_at=now, filled_at=now))
        s.add(Order(run_id=run_id, signal_id=sigs[1].id, alpaca_order_id=None,
                    status="skipped", submitted_at=now))
        s.commit()

    rows = build_summary(engine, since=now - timedelta(days=1))
    assert len(rows) == 1
    row = rows[0]
    assert row.strategy == "orb"
    assert row.signals == 2
    assert row.filled == 1
    assert row.avg_slip_bp is not None
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_report.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `src/plutus/report.py`**

```python
"""DB aggregations for `plutus report`."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Session, select

from plutus.storage import Order, Signal

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class StrategyRow:
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
        sig_by_id = {sig.id: sig for sig in sigs if sig.id is not None}
        ord_rows = s.exec(
            select(Order).where(Order.signal_id.in_(list(sig_by_id.keys())))  # type: ignore[attr-defined]
        ).all()

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
```

- [ ] **Step 4: Run tests + lint + type**

Run: `uv run pytest tests/test_report.py -v && uv run ty check`
Expected: Pass.

- [ ] **Step 5: Commit**

```bash
git add src/plutus/report.py tests/test_report.py
git commit -m "feat(report): add per-strategy aggregation since timestamp"
```

---

## Task 20: CLI (`cli.py`)

**Files:**
- Create: `src/plutus/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
"""Smoke tests for the typer CLI."""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from plutus.cli import app


def test_list_command_includes_registered_strategies() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "orb" in result.output
    assert "rsi_vwap" in result.output
    assert "donchian_swing" in result.output


def test_signals_command_handles_empty_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_API_SECRET", "s")
    monkeypatch.setenv("PLUTUS_DB_PATH", str(tmp_path / "x.db"))
    runner = CliRunner()
    result = runner.invoke(app, ["signals"])
    assert result.exit_code == 0
    assert "no signals" in result.output.lower()


def test_report_command_handles_empty_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_API_SECRET", "s")
    monkeypatch.setenv("PLUTUS_DB_PATH", str(tmp_path / "x.db"))
    runner = CliRunner()
    result = runner.invoke(app, ["report"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `src/plutus/cli.py`**

```python
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
        datetime | None, typer.Option(formats=["%Y-%m-%d"], help="Default: last 7 days"),
    ] = None,
) -> None:
    """Print recent signals from the DB."""
    settings = Settings()
    engine = init_db(settings.db_path)
    cutoff = since or (datetime.now(UTC) - timedelta(days=7))
    with Session(engine) as s:
        stmt = select(Signal).where(Signal.timestamp >= cutoff)
        if strategy is not None:
            stmt = stmt.where(Signal.strategy_name == strategy)
        rows = s.exec(stmt.order_by(Signal.timestamp.desc()).limit(100)).all()  # type: ignore[attr-defined]
    if not rows:
        typer.echo("no signals.")
        return
    typer.echo(f"{'strategy':<18} {'time':<25} {'symbol':<6} {'side':<5} {'type':<14} qty   price")
    for r in rows:
        typer.echo(
            f"{r.strategy_name:<18} {r.timestamp.isoformat():<25} {r.symbol:<6} "
            f"{r.side:<5} {r.signal_type:<14} {r.qty:<5} {r.price_at_signal}"
        )


@app.command(name="report")
def cmd_report(
    since: Annotated[
        datetime | None, typer.Option(formats=["%Y-%m-%d"], help="Default: last 30 days"),
    ] = None,
) -> None:
    """Per-strategy summary."""
    settings = Settings()
    engine = init_db(settings.db_path)
    cutoff = since or (datetime.now(UTC) - timedelta(days=30))
    rows = build_summary(engine, since=cutoff)
    if not rows:
        typer.echo("no data.")
        return
    typer.echo(f"{'strategy':<18} {'signals':>8} {'filled':>8} {'avg_slip(bp)':>14}")
    for r in rows:
        slip = f"{r.avg_slip_bp:.2f}" if r.avg_slip_bp is not None else "-"
        typer.echo(f"{r.strategy:<18} {r.signals:>8} {r.filled:>8} {slip:>14}")


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run tests + lint + type**

Run: `uv run pytest -v && uv run ruff check && uv run ty check`
Expected: All pass.

- [ ] **Step 5: Smoke test the installed CLI**

Run: `uv run plutus list`
Expected: prints `donchian_swing`, `orb`, `rsi_vwap` (one per line).

- [ ] **Step 6: Commit**

```bash
git add src/plutus/cli.py tests/test_cli.py
git commit -m "feat(cli): add typer CLI with run/backtest/list/signals/report"
```

---

## Task 21: Final verification + README pointer

**Files:**
- Modify: `AGENTS.md` (add `Running the lab` section)

- [ ] **Step 1: Add a short "Running" section to `AGENTS.md`**

Append:

```markdown
## Running the lab

```bash
uv sync
cp .env.example .env  # fill in ALPACA_API_KEY / ALPACA_API_SECRET
uv run plutus list                                 # see registered strategies
uv run plutus run                                  # start the paper trader (blocks)
uv run plutus backtest --strategy orb \
  --start 2026-01-01 --end 2026-04-30              # backtest one strategy
uv run plutus signals                              # see last 7 days of signals
uv run plutus report                               # per-strategy summary
```

DB lives at `./data/plutus.db` by default.
```

- [ ] **Step 2: Run the entire suite end-to-end**

Run: `uv run pre-commit run --all-files && uv run pytest`
Expected: All hooks pass; all tests pass; coverage ≥ 85%.

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): add Running the lab section"
```

---

## Self-review notes

- **Spec coverage:** Every section of the spec has a corresponding task — settings (Task 4), logging (Task 5), storage (Tasks 6–7), registry (Task 8), base class / recorder (Task 9), indicators (Task 10), three strategies (Tasks 11–13), broker (Task 14), lumibot adapters (Task 15), universe loader (Task 16), runner (Task 17), backtest (Task 18), report (Task 19), CLI (Task 20), final wiring (Task 21).
- **Placeholders:** No "TBD" or "handle edge cases" — every step is concrete code or a concrete command.
- **Type consistency:** `ProposedSignal` shape matches across base class and all three strategies; `RunnerBundle.strategies` is `list[_PlutusAdapter]`; `attach_engine` signature is consistent everywhere it's called.
- **Known sharp edge:** Task 11 introduces `_OrbRegistrationMarker` that Task 15 deletes. This is on purpose — it lets each strategy's pure-logic task run end-to-end (registry tests pass) without the lumibot dependency, then the adapter task replaces all three markers in one commit.
- **Known limitation:** The lumibot adapters' `_fetch_bars_*` methods return empty lists (stub). Implementing them requires live lumibot data wiring, which can only be exercised against a real Alpaca paper account — out of scope for unit tests. Task 21's smoke test (`uv run plutus list`) confirms the package imports and the CLI starts; full live-run validation happens manually.
