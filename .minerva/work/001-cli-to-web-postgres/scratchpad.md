# Scratchpad — 001-cli-to-web-postgres

## Notes


## Panel decisions 2026-06-13

- [user-resolved escalation → 2/3 accept] scope check: single unit confirmed — runner.py in scope; Doppler everywhere (no .env in any env); user chose "Doppler everywhere"
- [2/3 accept, Skeptic dissented] approach selection: FastAPI + uvicorn + psycopg[binary] (psycopg3); implementation constraints: get_session try/finally, BaseHTTPMiddleware for request_id, /signals limit capped at 500
- [2/3 accept, Skeptic dissented, Arbiter amendment] whole-proposal acceptance: 001-cli-to-web-postgres accepted with amendment — only web service calls create_all(); worker assumes tables exist
