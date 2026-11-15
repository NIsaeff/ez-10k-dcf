# EZ-10k — Agentic DCF

enter a ticker, pull the company's latest 10-K financials from SEC EDGAR, and compute a discounted cash flow valuation in the chat UI. Currently Application only includes a couple tickers for now, the plan is to be fully compatible. `AAPL`, `MSFT`, `GOOGL`, `AMZN`, `NVDA`, `META`, `TSLA`, `KO`, `PWR`.

Unknown tickers return a clear `422 unsupported_ticker` — no guessed valuation.

## Quickstart

```bash
# 1. Python deps
uv sync

# 2. Frontend deps + production build (FastAPI serves dist/)
cd frontend && bun install && bun run build && cd ..

# 3. Environment: copy the schema and fill in real values
cp .env.example .env
#   OPENAI_API_KEY / OPENAI_BASE_URL / LLM_MODEL  (OpenAI-compatible LiteLLM proxy)
#   SEC_USER_AGENT="EZ-10k Capstone (you@example.com)"

# 4. Run
./scripts/dev-backend.sh # or cd backend then uv run fastapi dev

# open http://localhost:8001 and type any question about investments or the stock market
```
# WARNING: DO NOT TAKE ANY INVESTMENT ADVICE FROM THIS APP, IT IS REALLY BAD AND DUMB
(for now but still dont even if its good lol)

Frontend-only dev loop (HMR (Hot Module Replacement) on the port in `.env`, proxy to the API port):

```bash
./scripts/dev-mcp.sh          # terminal 1 — FRED MCP sidecar, port from FRED_MCP_PORT
./scripts/dev-backend.sh      # terminal 2 — API, port from PORT in .env
cd frontend && bun run dev    # terminal 3 — UI, port from FRONTEND_PORT
```

`uv run` does not read `.env` and `fastapi dev` resolves its port before any app
code runs, so the wrapper just adds `--env-file .env`. The equivalent raw command is
`uv run --env-file .env fastapi dev app/main.py`; the frontend needs no flag.
`set -a; . ./.env; set +a` in a shell also makes the raw commands work.

## What is a Discounted Cash Flow?

Discounted Cash Flow (DCF) is a valuation technique to value any corporation, company, organization or even a particular project within an org to find its intrinsic value. It works by taking your own forcasts for future growth then discounting that growth based on how far in the future it is. You can think of "Discounting" as essentailly adjusting the price based on benchmarking future value relative to other opportunities, such as investing in "gauranteed" treasuries or bonds or other stocks or ventures. 

The whole goal with this is to try to find the intrinsic or "true" value of something based on your own particular analysis or (non-insider) information. Once you perform you analisis you can then choose to: 
- buy or hold if your value is larger thatn the markets or
- sell/not-buy if your value is smaller than the market's.

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
- **Market inputs.** Beta, price and the risk-free rate come from Yahoo; cost of debt
  comes from SEC `InterestExpense`. Every CAPM input carries a `source` string.

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
| `POST /api/chat` | `{messages}` → `{reply, valuation}`; detects allowlisted tickers |
| `GET /api/health` | status, model, supported tickers |
| `GET /docs` | Swagger UI |

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
app/
  main.py              FastAPI routes + frontend mount
  config.py            pydantic-settings (.env)
  schemas.py           request/response models
  llm.py               provider client + narration/fallback
  services/
    edgar.py           SEC client, XBRL helpers, cache
    financials.py      tag mapping → raw annual rows
    dcf.py             pure FCFF/DCF math
    valuation.py       orchestration + WACC defaults
    fred_mcp.py        MCP client for FRED macro tools (child process)
frontend/              React 19 + Vite + Tailwind 4 + shadcn (Base UI/Mira)
scripts/
  check_llm.py         provider smoke test
  analyze_all.py       run all 9 tickers
  make_fixtures.py     rebuild trimmed SEC test fixtures
tests/                 pytest + fixtures
docs/
  capstone-plan.md     phases, blockers, Definition of Done
  valuation-spec.md    frozen schema + formulas
  qa-report.md         9-ticker results and limitations
```

## Tests and checks

```bash
uv run pytest -q
uvx ruff check app scripts tests
cd frontend && bunx tsc --noEmit && bun run build
uv run python -m scripts.check_llm          # one live provider call
uv run python -m scripts.analyze_all        # all 9 tickers
```

## Assumptions and limitations

- WACC is a manual default per ticker, shown on the card; CAPM/auto market data is
  deferred.
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

## Reference

The earlier full-stack template is preserved on the `template-scaffold` branch. The
Dash reference app lives at `~/development/dcf-ai-calculator`.
