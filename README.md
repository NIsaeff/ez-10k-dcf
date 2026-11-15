# EZ-10k — Agentic DCF

Enter a ticker, pull the company's latest 10-K financials from SEC EDGAR, and value it
with a discounted cash flow model whose every input you can inspect.

**Supported today:** `AAPL`, `MSFT`, `GOOGL`, `AMZN`, `NVDA`, `META`, `TSLA`, `KO`,
`PWR`. The ticker box searches all ~10,400 SEC filers; the valuation engine is limited to
these nine while the remaining XBRL tag paths are mapped. Unknown tickers return a clear
`422 unsupported_ticker` — no guessed valuation.

**Status:** phases 1–8 complete (backend, DCF, SEC extraction, API, UI, QA, drill-down
provenance, DCF Wizard), plus the narrative layer: docked chat panel, 10-K Analysis with
quoted claims, wizard proposals with before/after impact, and FRED macro context. The
submission artifacts (assignment writeup, demo video) remain.

## Quickstart

```bash
# 1. Python deps — uv workspace root; the project itself is backend/
uv sync

# 2. Frontend deps + production build (FastAPI serves dist/)
cd frontend && bun install && bun run build && cd ..

# 3. Environment: copy the schema and fill in real values
cp .env.example .env
#   OPENAI_API_KEY / OPENAI_BASE_URL / LLM_MODEL   (OpenAI-compatible LiteLLM proxy)
#   FRED_API_KEY                                   (free: fredaccount.stlouisfed.org/apikeys)
#   SEC_USER_AGENT="EZ-10k Capstone (you@example.com)"

# 4. Run — macro sidecar in one terminal, API in another (from the repo root)
./backend/scripts/dev-mcp.sh          # FRED sidecar the chat's macro tools talk to
./backend/scripts/dev-backend.sh

# open http://localhost:8000 — ask about a ticker, or click through the wizard
```

Without `./scripts/dev-mcp.sh` the app still runs: the engine's risk-free rate falls back
to Yahoo `^TNX`, and the chat answers without macro tools.

> ⚠️ **DO NOT TAKE INVESTMENT ADVICE FROM THIS APP.** It is really bad and dumb
> (for now — but don't even if it gets good lol). Valuations here are a learning
> exercise, not a recommendation to trade.

Frontend-only dev loop (HMR — Hot Module Replacement — on the port in `.env`, proxy to
the API port):

```bash
./backend/scripts/dev-mcp.sh      # terminal 1 — FRED MCP sidecar, port from FRED_MCP_PORT
./backend/scripts/dev-backend.sh  # terminal 2 — API, port from PORT in .env
cd frontend && bun run dev        # terminal 3 — UI, port from FRONTEND_PORT
```

`uv run` does not read `.env` and `fastapi dev` resolves its port before any app
code runs, so the wrapper just adds `--env-file .env`. The equivalent raw command is
`uv run --env-file .env fastapi dev app/main.py`; the frontend needs no flag.
`set -a; . ./.env; set +a` in a shell also makes the raw commands work. With no
`.env` at all, both sides fall back to their code defaults: API on 8000, vite on 5173.

## What is a Discounted Cash Flow?

Discounted Cash Flow (DCF) is a valuation technique to value any corporation, company, organization or even a particular project within an org to find its intrinsic value. It works by taking your own forecasts for future growth then discounting that growth based on how far in the future it is. You can think of "Discounting" as essentially adjusting the price based on benchmarking future value relative to other opportunities, such as investing in "guaranteed" treasuries or bonds or other stocks or ventures. 

The whole goal with this is to try to find the intrinsic or "true" value of something based on your own particular analysis or (non-insider) information. Once you perform your analysis you can then choose to:

- buy or hold if your value is larger than the market's, or
- sell/not buy if your value is smaller than the market's.

## How it works

```
React chat (Vite) ──/api/chat──▶ FastAPI
                                  ├─ ticker detection
                                  ├─ SEC EDGAR: ticker → CIK → latest 10-K
                                  ├─ XBRL → annual financials (tag fallbacks)
                                  ├─ FCFF → growth fade → terminal value → per-share
                                  └─ LLM narrates the computed JSON (never invents numbers)
```

- **Numbers are deterministic.** `app/services/dcf.py` is pure Python; the LLM only
  formats the finished result.
- **Every number is traceable.** `source_facts` records the XBRL tag, period, filing
  date, and accession behind each input, and the card expands to show them.
- **Fail loudly.** Missing required data returns `422` with `missing_fields`.
- **Cache.** SEC and Yahoo responses live in `data/raw/` (gitignored); tests use trimmed
  fixtures and never touch the network.
- **Market inputs.** Beta and price come from Yahoo; the risk-free rate comes from FRED
  `DGS10`, with Yahoo `^TNX` only as the fallback; cost of debt comes from SEC
  `InterestExpense`. Every CAPM input carries a `source` string.
- **Proposals, not edits.** The AI can propose an assumption change (`growth` 1.2% →
  1.5%) or a navigation, with a rationale, optional filing evidence, and the per-share
  impact **recomputed by the engine**. Nothing moves until you press ✓; every proposal
  carries a confidence score that tints its card.

## API

| Route | Purpose |
|---|---|
| `POST /api/analyze/{ticker}` | Deterministic `ValuationResult` |
| `POST /api/dcf/{ticker}` | Recalculate with assumption overrides |
| `POST /api/dcf/{ticker}/sensitivity` | WACC × terminal-growth grid |
| `GET /api/wacc/{ticker}` | CAPM/WACC decomposition with per-input sources |
| `GET /api/tickers?q=` | Ticker search over SEC's universe, pilots ranked first |
| `GET /api/filing/{ticker}` | Parsed 10-K blocks + a hierarchy of quoted claims |
| `GET /api/filing/{ticker}/document` | Sanitised same-origin filing for the viewer |
| `GET /api/assumptions/{ticker}` | Filing evidence for an engine assumption (growth pilot) |
| `POST /api/chat` | `{messages, context?}` → `{reply, trace, sources, proposals, valuation}` |
| `GET /api/health` | status, model, supported tickers, FRED sidecar state |
| `GET /docs` | Swagger UI |

`/api/chat` takes the wizard's current state as `context` so the model can reason about
deltas ("raise growth by 0.25pp") instead of guessing absolute values, and returns each
tool call in `trace` with its input, output, status and duration. `proposals` is the
human-in-the-loop queue: `{id, kind, changes[{key, label, before, after, confidence}],
rationale, evidence, impact, confidence}`. Applying one is a frontend action — the API
never applies it.

Routes: `/` redirects to `/wizard`. The DCF Wizard (FCFF, WACC, DCF tabs) keeps its
state in search params so a valuation is linkable; `/filing` is 10-K Analysis (claim tree
plus the rendered filing, verbatim quotes highlighted in place; `?claim=<id>` opens a
specific claim). The AI chat is a docked right-hand panel, toggled from each page header
and persisted in localStorage, not a route of its own. The wizard's ticker box searches all
~10,400 SEC filers, with the 9 pilot tickers listed first by default; chat stays on the
pilot allowlist.

## Macro data (FRED MCP)

The chat can query macro series — Treasury yields, CPI, GDP, unemployment — through the
third-party [`fred-mcp-server`](https://github.com/stefanoamorelli/fred-mcp-server)
(AGPL-3.0). It runs as a long-lived HTTP sidecar (`./scripts/dev-mcp.sh`); none of its
code is imported or vendored into this repo.

- **This app owns `FRED_API_KEY`.** `app/config.py` reads it from `.env` and forwards it
  to the sidecar's environment, so the key has exactly one owner.
- **One process, warm cache.** The sidecar caches upstream FRED responses
  (`FRED_CACHE_TTL_MS`) and enforces FRED's 120 req/min budget in one place, and both
  survive app reloads. A per-call stdio spawn discards that state every request, which
  made each chat turn cost 3 process launches; `FRED_MCP_TRANSPORT=stdio` restores the
  old behaviour for comparison.
- The server's own schemas (`fred_search`, `fred_browse`, `fred_get_series`) are turned
  into OpenAI `tools` at runtime, so upstream tool changes need no code change here.
- `app/llm.py` runs up to 4 tool rounds. `/api/chat` returns a `trace` (each call's
  input, output, status and duration) plus `sources` (the series actually fetched), and
  the chat renders them with the shadcn AI Elements *Chain of Thought* → *Tool* → *Sources*
  patterns, so a lookup is inspectable rather than invisible.
- If the sidecar is down, `/api/health` reports `fred_mcp: "down"` and the chat answers
  without tools instead of erroring.

Launch note: `fred-mcp-server` 1.2.0 only boots when Node receives the **real** path of
its entrypoint — its `isMainModule` guard compares `import.meta.url` with
`process.argv[1]`, and `npx` puts a symlink on `PATH`, so plain `npx fred-mcp-server`
exits silently. Both `app/services/fred_mcp.py` and `scripts/dev-mcp.sh` resolve the
symlink before launching.

```ini
FRED_API_KEY=...                    # required — https://fredaccount.stlouisfed.org/apikeys
FRED_MCP_URL=http://127.0.0.1:3101/mcp   # sidecar endpoint, one per worktree
FRED_MCP_PORT=3101                       # port the sidecar binds
FRED_CACHE_TTL_MS=21600000               # 6h; daily/monthly series barely move intraday
FRED_MCP_ENABLED=true               # false = keep the chat LLM-only
FRED_MCP_PACKAGE=fred-mcp-server    # pin if needed, e.g. fred-mcp-server@1.2.0
FRED_MCP_TRANSPORT=http             # stdio = spawn per call (no shared cache)
```

### Engine inputs (deterministic)

`app/services/macro.py` is the other FRED path — plain HTTPS, not MCP — for numbers
the engine consumes rather than text the model writes:

- `DGS10` supplies the CAPM risk-free rate. `/api/wacc` labels it
  `fred: DGS10 <observation date>`, and Yahoo `^TNX` is only the fallback when FRED is
  unavailable or the observation is stale (stale FRED still beats nothing).
- Every `ValuationResult` carries a `macro` snapshot — `complete` / `degraded` /
  `absent` — with `as_of`, per-series value/units/date/url, and flags such as
  `macro_real_gdp_stale`. `absent` is stated, never implied.
- Cache: `data/raw/fred/<series>.json`, 6h TTL, stale-served when a refresh fails.
- Freshness bounds per series: dailies 7 days, monthlies 45, quarterly GDP 180.

## Layout

```
serve.py                  entrypoint for hosts that start one process from the root (Databricks)
app.yaml                  Databricks Apps command, health check, env
databricks.yml            Declarative Automation Bundle (app + secret scope)
package.json              build shim: the platform only looks for a root package.json
pyproject.toml            uv workspace root, member = backend
uv.lock                   one lockfile for the workspace
backend/                  the FastAPI project
  app/
    main.py               FastAPI routes + SPA mount
    config.py             pydantic-settings (.env, overridden by real env vars)
    schemas.py            request/response models (the wire contract)
    llm.py                provider client, tool loop, narration + fallback
    services/
      edgar.py            SEC client, XBRL helpers, cache
      financials.py       tag mapping → raw annual rows
      dcf.py              pure FCFF/DCF math
      valuation.py        orchestration + WACC defaults
      wacc.py             CAPM decomposition with per-input sources
      market.py           Yahoo beta/price + FRED risk-free with fallbacks
      macro.py            deterministic FRED series (plain HTTPS, engine inputs)
      fred_mcp.py         MCP client for the chat's FRED tools (child process)
      filing.py           10-K fetch, sanitise, block parsing, disk cache
      claims.py           quoted-claim hierarchy + evidence extraction
      assumptions.py      filing evidence for a single engine assumption
      wizard_proposals.py proposal validation, effective values, engine impact
  scripts/
    dev-backend.sh        API on PORT, with --env-file <repo>/.env
    dev-mcp.sh            FRED MCP sidecar on FRED_MCP_PORT
    check_llm.py          provider smoke test
    analyze_all.py        run all 9 tickers
    make_fixtures.py      rebuild trimmed SEC test fixtures
    dump_engine_reference.py  engine snapshot for the frontend parity check
  tests/                  pytest + trimmed SEC fixtures (no network)
frontend/                 React 19 + Vite + Tailwind 4 + shadcn (Base UI/Mira)
  src/routes/             file-based routes: wizard, filing, index redirect, __root
  src/components/wizard/  FCFF / WACC / DCF panels + sensitivity grid
docs/
  capstone-plan.md        phases, blockers, Definition of Done
  valuation-spec.md       frozen schema + formulas
  qa-report.md            9-ticker results and limitations
```

The split follows the [FastAPI full-stack template](https://github.com/fastapi/full-stack-fastapi-template).
Anything the two halves share — `.env`, `frontend/dist`, `data/` — sits at the repo root,
which is why `backend/app/config.py` resolves paths from `backend/`.

## Tests and checks

```bash
uv run --directory backend pytest -q
(cd backend && uvx ruff check app scripts tests)   # run from backend/: ruff infers
                                                   # first-party packages from cwd
(cd frontend && bunx tsc --noEmit && bun run build)
uv run --directory backend python -m scripts.check_llm     # one live provider call
uv run --directory backend python -m scripts.analyze_all   # all 9 tickers
```

160 tests, all offline: SEC and Yahoo responses come from trimmed fixtures in
`tests/fixtures/`, and `macro.py`'s fetcher is monkeypatched. `ruff`, `tsc` and the
production build are part of the gate as well. CI runs the same gate on every pull
request (`.github/workflows/ci.yml`), using `npm ci` for the frontend so it matches what
Databricks runs at deploy time.

`main` is protected: changes land through a pull request, both CI jobs are required,
squash-merge only, no force-pushes and no deletions. A direct `git push` is refused
server-side, so the habit is:

```bash
git switch -c feat/whatever
# ...work...
git push -u origin feat/whatever
gh pr create --fill && gh pr merge --squash --delete-branch
```

Dependency updates are covered by Dependabot for `github-actions` and `bun`. Python is
manual, because there is no `uv` ecosystem and the `pip` ecosystem can't regenerate
`uv.lock`: `uv lock --upgrade`.

## Deployment

Target platform is **Databricks Apps**, which builds from the repo and would serve the
SPA from FastAPI the same way `./backend/scripts/dev-backend.sh` does. Two things have to differ
from local dev: no Node process at runtime (the chat's macro tools go over plain HTTPS
through `app/services/macro.py`), and an ephemeral filesystem (`DATA_DIR` points at
`/tmp`, so the filing and FRED caches are per-container and recompute after a restart).
The packaging is in place: `serve.py` binds `DATABRICKS_APP_PORT`, `app.yaml` declares
the command and health check, and `databricks.yml` deploys the app plus its secret scope.
The SPA is built during deployment from `frontend/package-lock.json` (npm), so
regenerate that lockfile whenever frontend dependencies change:

```bash
npm install --package-lock-only --prefix frontend   # after a bun add/remove
```

Runbook, including the secret scope and bundle commands: [`docs/databricks.md`](docs/databricks.md).

## Assumptions and limitations

- Default WACC is a manual per-ticker value, shown on the card. `GET /api/wacc` does
  compute a full CAPM breakdown (beta from Yahoo, risk-free from FRED, cost of debt from
  SEC) and the wizard shows it, but the default is not auto-applied.
- Growth is a faded historical FCFF CAGR; terminal growth is 2.5%.
- FCFF base is a normalized 5-year average (outliers outside 0.5×–2× median removed).
- No persistence, auth, streaming, or real-time prices.
- Valuations are illustrative, **not investment advice**.

## Docs

- [`docs/capstone-plan.md`](docs/capstone-plan.md)
- [`docs/valuation-spec.md`](docs/valuation-spec.md)
- [`docs/qa-report.md`](docs/qa-report.md)
- [`docs/backlog.md`](docs/backlog.md) — understood but unscheduled work
- [`docs/narrative-layer.md`](docs/narrative-layer.md) — 10-K prose / AI recommendations
- [`docs/databricks.md`](docs/databricks.md) — deployment runbook

## Reference

The earlier full-stack template is preserved on the `template-scaffold` branch. The
Dash reference app lives at `~/development/dcf-ai-calculator`.
