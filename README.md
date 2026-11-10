# Parsity Capstone — 10-K DCF

Capstone project: pull a company's 10-K, extract the financials, and build a
discounted cash flow (DCF) valuation.

Started from scratch as a minimal FastAPI app. Dependencies get added one at a
time, only when the app actually needs them.

## Status

Hello world — one HTML page, one health endpoint. No database, no frontend
build, no auth.

## Quickstart

```bash
uv sync
uv run fastapi dev app/main.py
```

- Page: <http://localhost:8000>
- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/api/health>

## Layout

```
app/main.py      the entire app for now
pyproject.toml   dependencies (fastapi only)
```

## Dependency ladder

Added one step at a time, when a feature needs it:

| # | Dependency | Trigger |
|---|---|---|
| 1 | `fastapi[standard]` | now |
| 2 | `pydantic-settings` | first real config value / `.env` |
| 3 | `sqlmodel` + Postgres | first persistence |
| 4 | `alembic` | first schema change worth migrating |
| 5 | React + Vite | when server-rendered HTML stops being enough |
| 6 | auth (JWT or session) | when there are real users |

## Reference: full-stack template

The earlier scaffold (FastAPI template + local `AUTH_DISABLED` flag) is
preserved on the `template-scaffold` branch:

```bash
git worktree add ../fsft-template template-scaffold   # browse/run it
git show template-scaffold:backend/app/main.py        # read a single file
```

Upstream: <https://github.com/fastapi/full-stack-fastapi-template>
