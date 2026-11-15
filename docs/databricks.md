# Deploying to Databricks Apps

Runbook for putting EZ-10k on Databricks Apps. Written against the Databricks docs as
of November 2026.

**Status:** not deployed yet. The packaging files (`serve.py`, `app.yaml`,
`databricks.yml`, root `package.json`) land in the commit after this doc; everything
below is the target state they implement.

## Layout constraint: `backend/` + `frontend/`

The repo follows the FastAPI full-stack template, with the Python project in `backend/`
and the SPA in `frontend/`. Databricks inspects **one** app directory and runs its build
steps from there, so the app source path has to be the **repo root** — that's the only
place a root `package.json` can trigger the SPA build.

That means `uv sync` must also be able to run at the root. `backend/pyproject.toml` stays
the project, and the root becomes a **uv workspace root**:

```toml
# pyproject.toml (repo root)
[tool.uv.workspace]
members = ["backend"]
```

`uv sync` at the root then installs the workspace (backend's dependencies) into a single
root `.venv`, and `uv.lock` moves back to the root. Local work still happens in
`backend/`: `uv sync` finds the workspace root on its own, so `uv run --directory backend`
keeps working unchanged.

One more consequence: with the code in `backend/app/`, the process needs `backend/` on
`sys.path`. `serve.py` does that explicitly rather than relying on the working directory.

## What the runtime gives you

| | |
|---|---|
| OS / runtime | Ubuntu 22.04, Node 22, `uv` 0.13.5 preinstalled |
| Python | `pip`-based apps are pinned to 3.11. **`uv`-based apps honour `requires-python`**, so our 3.13 pin is respected |
| Compute | 2 vCPU / 6 GB by default (standard app) |
| Port | your process must listen on `$DATABRICKS_APP_PORT` |
| Filesystem | **ephemeral** — no state survives a restart or a scale event |
| Egress | allowed by default; SEC, Yahoo and FRED are reachable without extra config |

## How the build runs

Databricks inspects the repo and runs a fixed sequence — this is not configurable, and
it's why the repo layout matters:

| Detected | Step |
|---|---|
| `package.json` at the **repo root** | `npm install`, then later `npm run build` |
| `pyproject.toml` + `uv.lock` at the app root, no `requirements.txt` | `uv sync` |
| `app.yaml` | the start `command`, after the build steps |

So the SPA is built **before** the app process starts, which is what
`backend/app/main.py`'s `if settings.frontend_dist.is_dir()` check needs: it decides at import
time whether to mount the SPA. If the build were skipped, the app would start
successfully and serve a "Frontend not built" stub — a silent failure, not a crash.

### The root `package.json` shim

`frontend/package.json` alone is invisible to the build (only the root is inspected).
The root manifest exists solely to trigger the Node branch and hand off to bun, so
`bun.lock` stays the single source of truth:

```json
{
  "name": "ez-10k-dcf",
  "private": true,
  "scripts": {
    "build": "cd frontend && npx -y bun@1.4.4 install --frozen-lockfile && npx -y bun@1.4.4 run build"
  }
}
```

`frontend/dist` stays gitignored; nothing is committed from the build.

## Files

| File | Purpose |
|---|---|
| `serve.py` | entrypoint: reads `DATABRICKS_APP_PORT`, runs uvicorn with `proxy_headers=True` |
| `app.yaml` | `command`, health check, non-secret env |
| `databricks.yml` | Declarative Automation Bundle: app resource + secret scope |
| `.python-version` | `3.13` — read by uv on both sides |
| root `package.json` | the build shim above |

`app.yaml`:

```yaml
command: ['python', 'serve.py']
health_check:
  path: /api/health
  timeout_seconds: 120
env:
  - name: SEC_USER_AGENT
    value: 'EZ-10k Capstone (you@example.com)'
  - name: OPENAI_BASE_URL
    value: 'https://parsity-litellm.fly.dev'
  - name: LLM_MODEL
    value: 'gpt-6-luna'
  - name: DATA_DIR
    value: '/tmp/ez10k'
  - name: FRED_MCP_ENABLED
    value: 'false'
  - name: OPENAI_API_KEY
    valueFrom: openai-api-key
  - name: FRED_API_KEY
    valueFrom: fred-api-key
```

`SEC_USER_AGENT` must contain a real contact address. SEC returns **403** for generic
agents, which surfaces as "EDGAR is down" rather than an auth error.

`/api/health` returns 200 unconditionally (it reports `fred_mcp` state as data), which
makes it safe as the deployment health check.

## Secrets

No `.env` is uploaded. `app/config.py` uses pydantic-settings, where real environment
variables outrank the `.env` file — so injected values win with no code change.

```bash
databricks secrets create-scope ez-10k-dcf
databricks secrets put-secret ez-10k-dcf openai-api-key    # prompts, never echoed
databricks secrets put-secret ez-10k-dcf fred-api-key
```

The scope is attached to the app as a resource; `app.yaml`'s `valueFrom` resolves
resource keys, not raw secret names, so the names above must match the bundle's
resource block.

## FRED in production

Locally the chat reaches FRED through the `fred-mcp-server` sidecar (Node, AGPL-3.0).
That doesn't ship:

- there's no long-lived sidecar process — the app gets one entrypoint;
- spawning Node per tool call would add seconds to every chat turn;
- running an AGPL server as a network service has licensing questions this project
  doesn't need to answer.

Instead, `FRED_MCP_ENABLED=false`, and `app/services/macro.py` — the plain-HTTPS client
the engine already uses for the risk-free rate — exposes the same tool surface to the
chat. Same key, same cache location, no Node.

## Data

`DATA_DIR=/tmp/ez10k` keeps the caches writable:

- `raw/filings/` — fetched 10-K text
- `raw/market/` — Yahoo responses
- `raw/fred/` — FRED series (6 h TTL)
- `xbrl/` — extracted facts

All of it is per-container. The expensive one is 10-K claim extraction (~60 s cold,
cached per accession): after a restart, the first `/api/filing` request pays that again.
If that becomes annoying, attach a Unity Catalog Volume and point `DATA_DIR` at
`/Volumes/<catalog>/<schema>/ez10k` — same code path, persistent storage.

## Deploy

```bash
# once
databricks auth login --host https://<workspace>.cloud.databricks.com
databricks bundle deploy -t prod
databricks bundle run ez-10k-dcf -t prod      # or: databricks apps deploy ez-10k-dcf

# logs
databricks apps logs ez-10k-dcf
```

Deploying from local avoids the Git-credential setup that a Git-backed app needs (the
app's service principal requires a credential for a private repo). Auto-deploy on push
is available later if it earns its keep — it requires a **private** repo and the
Databricks GitHub app installed on it.

## Smoke test after deploy

1. `GET /api/health` → `200`, `llm_configured: true`, `fred_mcp` reported as disabled
2. Hard refresh `/wizard?ticker=KO` → SPA loads (proves the catch-all route works)
3. DCF tab renders and `POST /api/dcf/KO` returns the same per-share value as local
4. One chat turn → reply plus a `trace`; ask for a growth change → proposal card with
   ✓/✗ and a `$before → $after` impact
5. `/filing?ticker=KO` → claim tree plus the document iframe (the slowest cold path)

## Gotchas

- **Catch-all ordering.** `backend/app/main.py` registers the SPA route last so `/api/*`
  wins. Anything that re-registers it earlier will swallow API 404s and return HTML.
- **`frontend/dist` is gitignored.** That's the point of the build shim; don't
  "fix" it by committing the bundle.
- **Health check is not readiness for the LLM.** A bad `OPENAI_API_KEY` still returns
  200 from `/api/health` (it only reports whether one is set). The chat is the real test.
- **`uv sync` installs the dev group**, so `pytest` ends up in the image. Harmless, a
  few MB; `[tool.uv] default-groups = []` would trim it if that matters.
