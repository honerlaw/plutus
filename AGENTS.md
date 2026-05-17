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
