# 001-cli-to-web-postgres

## Status
Shipped (2026-06-13)

## Goal
Convert Plutus from a CLI/SQLite local application to a minimal FastAPI web app backed by PostgreSQL, deployable on Digital Ocean App Platform with secrets managed by Doppler.

## Why
The CLI/SQLite approach limits observability and shareability. A web API makes signals and reports accessible without SSH access. PostgreSQL + Digital Ocean enables a persistent, cloud-hosted instance without manual server management.

## Approach
FastAPI service + DO App Platform worker. Doppler injects all env vars at runtime — no `.env` file loading in any environment. Developers use `doppler run -- uv run ...` locally.

**In-scope changes:**

1. `config.py` — replace `db_path: Path` → `database_url: str` (alias `PLUTUS_DB_URL`); drop `env_file` from `SettingsConfigDict` entirely
2. `storage/db.py` — `init_db(url: str) -> Engine`; PostgreSQL via `create_engine(url)`
3. `storage/models.py` — strip `sqlite_autoincrement` from `Signal.__table_args__` and `Order.__table_args__`; on `DailyRunSummary` keep `UniqueConstraint`, drop the `sqlite_autoincrement` dict entry
4. `runner.py` — `init_db(settings.database_url)` (was `settings.db_path`)
5. NEW `src/plutus/web.py`:
   - `lifespan` context manager: calls `create_all()` at startup (**only the web service runs DDL** — worker assumes tables exist), stores engine in module-level typed variable
   - `get_session` dependency: `try: yield Session(engine) finally: session.close()`; `RuntimeError` if engine is None at request time
   - `BaseHTTPMiddleware` (starlette.middleware.base) for `request_id = str(uuid4())` binding via `contextvars` into structlog per-request; no `run_id` on web layer (worker-only — intentional)
   - Endpoints: `GET /health` (SELECT 1 ping → 200 `{"status":"ok","db":"ok"}` or 503 `{"status":"error","db":"unreachable"}`), `GET /strategies`, `GET /signals?since=&strategy=&limit=100` (ISO 8601 date; server cap `Query(default=100, le=500)`), `GET /report?since=` (ISO 8601 date; default 30 days back)
   - Pydantic `BaseModel` response types for all endpoints; explicit status codes
6. `pyproject.toml` — add `fastapi>=0.115`, `uvicorn>=0.30`, `psycopg[binary]>=3.1` (psycopg3; ships `py.typed` — required for `ty check --strict`); dev: `httpx>=0.27`; remove `typer` from main deps (keep as dev convenience or remove entirely)
7. `.do/app.yaml` — service (uvicorn, port 8080, HTTP health check on `/health`) + worker (long-running runner, restart-on-failure); Doppler as env source for `PLUTUS_DB_URL`, `ALPACA_API_KEY`, `ALPACA_API_SECRET`
8. `CLAUDE.md` / `README.md` — update quickstart to `doppler run -- uv run ...`; document `doppler` as required dev tool; add manual `export PLUTUS_DB_URL=postgresql://...` fallback for devs without Doppler
9. Tests — update existing config tests (no `db_path`); add `tests/test_web.py` using `httpx.TestClient` + `app.dependency_overrides[get_session]` with SQLite in-memory; note: SQLite tests do not cover PostgreSQL-specific behavior

**Implementation notes (as shipped):**
- `BaseHTTPMiddleware` clears contextvars before each bind to prevent bleed across requests
- DB password scrubbed from startup log via `make_url(...).render_as_string(hide_password=True)`
- Health check catches `SQLAlchemyError`, not bare `Exception`
- `.do/app.yaml` uses `uv sync --no-dev` to exclude dev deps from production image
- `PLUTUS_DB_URL` must use `postgresql+psycopg://` scheme for psycopg3 routing; documented in README

**Explicit non-decisions:**
- Existing SQLite data is not migrated; production starts fresh on PostgreSQL (paper trading lab)
- Auth deferred — documented as internal tool, paper-only lab, no external users
- No Alembic — `create_all()` is sufficient for this project's current schema; first schema change will add Alembic at that time
- Only the web service calls `create_all()`; worker crashes fast if tables don't exist (DO restarts it)

## Success criteria

1. `uv run pytest` passes at ≥85% coverage with no warnings
2. `uv run ruff check` and `uv run ruff format --check` pass
3. `uv run ty check` passes in strict mode (psycopg3 `py.typed` satisfies this)
4. `GET /strategies` → 200 JSON list of 3 strategy names
5. `GET /signals` → 200 JSON array (empty is fine)
6. `GET /report` → 200 JSON per-strategy summary
7. `GET /health` → 200 `{"status":"ok","db":"ok"}`; 503 when DB unreachable
8. `PLUTUS_DB_URL` drives PostgreSQL connection; `PLUTUS_DB_PATH` / `db_path` are gone
9. `uv run pre-commit run --all-files` passes (incl. `paper=False` grep)
10. `.do/app.yaml` is present and syntactically valid YAML
11. No `env_file` anywhere in `config.py`
12. `uv lock --check` passes

## Open Questions
None blocking implementation.
