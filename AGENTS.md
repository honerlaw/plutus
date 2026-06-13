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
- Secrets are managed by **Doppler** — no `.env` file anywhere. In production, Doppler injects env vars. Locally, use `doppler run -- uv run ...` or export vars manually.
- No live-trading code paths anywhere — even disabled or behind a flag.

## Code style

- Strategies are deterministic pure functions of bar data. No randomness, no network calls inside `compute_signals`.
- DB access only inside `PlutusStrategy` base class and `report.py` — never in concrete strategy files.
- Prefer `sqlmodel` over raw SQL.
- Use `structlog` for all logging; bind `run_id` and `strategy_name` at the start of each run.
- Tests are TDD. Write the failing test first, run it to confirm it fails, then implement.

## Layout

See `docs/superpowers/specs/2026-05-17-plutus-trading-lab-design.md` for the architecture.

## Running the lab

Secrets are provided by Doppler. Install the [Doppler CLI](https://docs.doppler.com/docs/cli), then:

~~~bash
uv sync
# Option A: Doppler CLI (recommended)
doppler run -- uv run plutus list                  # see registered strategies
doppler run -- uvicorn plutus.web:app --reload     # start the web server (localhost:8000)
doppler run -- uv run plutus run                   # start the paper trader (blocks)

# Option B: manual export (no Doppler)
export ALPACA_API_KEY=...
export ALPACA_API_SECRET=...
export PLUTUS_DB_URL=postgresql+psycopg://user:pass@localhost/plutus  # +psycopg required for psycopg3
uv run uvicorn plutus.web:app --reload

# API endpoints (once the web server is running)
curl localhost:8000/strategies    # list strategies
curl localhost:8000/signals       # last 7 days of signals
curl localhost:8000/report        # per-strategy summary
curl localhost:8000/health        # health check
~~~

DB is PostgreSQL in production (via `PLUTUS_DB_URL`). For local dev, you can use SQLite: `export PLUTUS_DB_URL=sqlite:///./data/plutus.db`.

## minerva

This project uses [minerva](https://github.com/honerlaw/agent-marketplace/tree/main/plugins/minerva) for durable record discipline.

- `.minerva/knowledge/overview.md` — theme-grouped synthesis of everything known. Read first to orient (absent until `minerva:synthesize` first runs — fall back to the index).
- `.minerva/knowledge/index.md` — the catalog, one line per entry. Look up specifics here; drill into entries via their `[[NNN-type-slug]]` links only when a theme bears on your task.
- `.minerva/reference/` — present-tense operational docs (architecture, glossary, conventions): how the system works now. Read on demand.
- `.minerva/work/` — historical proposals and replans. Grep when you need the reasoning behind a past feature.

Active work units live at `.minerva/work/NNN-<slug>/`. Invoke the `minerva:using-minerva` skill (via the `Skill` tool) for the full methodology.

