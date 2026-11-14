# EZ-10k — Agentic DCF

Capstone project for the Parsity Dev Accelerator: enter a ticker, pull the company's
latest 10-K financials from SEC EDGAR, and compute a discounted cash flow valuation in
the chat UI.

**Status:** phases 1–8 complete (backend, DCF, SEC extraction, API, UI, QA, drill-down
provenance, DCF Wizard). Submission artifacts (assignment writeup + demo video) remain.

## Supported tickers

`AAPL`, `MSFT`, `GOOGL`, `AMZN`, `NVDA`, `META`, `TSLA`, `KO`, `PWR`.

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
uv run fastapi dev app/main.py
# open http://localhost:8000 and type: value KO
```

Frontend-only dev loop (HMR on :5173, proxy to :8000):

```bash
uv run fastapi dev app/main.py     # terminal 1
cd frontend && bun run dev         # terminal 2
```

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
| `POST /api/chat` | `{messages}` → `{reply, valuation}`; detects allowlisted tickers |
| `GET /api/health` | status, model, supported tickers |
| `GET /docs` | Swagger UI |

Routes: `/` is the chat, `/wizard` is the DCF Wizard (FCFF, WACC, DCF tabs; state lives
in search params so a valuation is linkable). The wizard's ticker box searches all
~10,400 SEC filers, with the 9 pilot tickers listed first by default; chat stays on the
pilot allowlist.

## Macro data (FRED MCP)

The chat can query macro series — Treasury yields, CPI, GDP, unemployment — through the
third-party [`fred-mcp-server`](https://github.com/stefanoamorelli/fred-mcp-server)
(AGPL-3.0). It runs as a separate Node process over stdio; none of its code is imported
or vendored into this repo.

- **This app owns `FRED_API_KEY`.** `app/config.py` reads it from `.env` and forwards it
  to the child process's environment, so the key has exactly one owner.
- The server's own schemas (`fred_search`, `fred_browse`, `fred_get_series`) are turned
  into OpenAI `tools` at runtime, so upstream tool changes need no code change here.
- `app/llm.py` runs up to 4 tool rounds. `/api/chat` returns `tools_used`, so the UI can
  show that a lookup actually happened.
- If the server is missing or fails, the chat answers without tools instead of erroring.

Launch note: `fred-mcp-server` 1.2.0 only boots when Node receives the **real** path of
its entrypoint — its `isMainModule` guard compares `import.meta.url` with
`process.argv[1]`, and `npx` puts a symlink on `PATH`, so plain `npx fred-mcp-server`
exits silently. `app/services/fred_mcp.py` resolves the symlink before launching.

```ini
FRED_API_KEY=...                    # required — https://fredaccount.stlouisfed.org/apikeys
FRED_MCP_ENABLED=true               # false = keep the chat LLM-only
FRED_MCP_PACKAGE=fred-mcp-server    # pin if needed, e.g. fred-mcp-server@1.2.0
```

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
