# EZ-10k — Capstone Plan

Status: v0.1 (planning). Owner: capstone repo (`parsity_capstone_10k_dcf`).

## Product

Type a ticker → pull the company's latest 10-K financials → compute FCFF/WACC/DCF →
the chat returns a valuation card with assumptions, history, and the filing source.

**Supported tickers (v1 allowlist):**

| Group | Tickers |
|---|---|
| Mag 7 | `AAPL`, `MSFT`, `GOOGL`, `AMZN`, `NVDA`, `META`, `TSLA` |
| Household products | `KO` |
| Industrial services | `PWR` |

Unknown tickers get a clear “unsupported ticker” response — never a guessed valuation.

**Explicit non-goals for v1:** auth, database/persistence, token streaming, real-time
market data (beta/price feeds), multi-company comparison, RAG over 10-K prose,
deployment.

## Architecture

```
React (Vite, shadcn) ──/api──▶ FastAPI
                                ├─ /api/chat        → ticker detection + narration
                                ├─ /api/analyze/{t} → deterministic ValuationResult
                                ├─ services/edgar.py     (ticker→CIK→10-K→XBRL)
                                ├─ services/financials.py (tag mapping, history)
                                ├─ services/dcf.py        (pure math)
                                └─ services/valuation.py  (orchestration)
```

Principles:

- **Numbers are deterministic.** The LLM narrates a computed `ValuationResult`; it does
  not generate or adjust figures.
- **Fail loudly, never fabricate.** Missing required data returns `422` with
  `missing_fields`; optional gaps become flags on the result.
- **No new dependency until needed.** Dependency ladder stays in the README.

See [`valuation-spec.md`](valuation-spec.md) for the frozen schema and formulas.

## Provider

OpenAI-compatible LiteLLM proxy (same as the course app):

- `OPENAI_BASE_URL=https://parsity-litellm.fly.dev`
- `OPENAI_API_KEY` — local `.env` only, never committed
- Chat model: `gpt-6-luna` (fallback probe if unavailable)

Config is read through `pydantic-settings`; `.env.example` documents names only.

## Phases

### Phase 1 — Contract + transport

1. Freeze schema/formulas in `docs/valuation-spec.md`. **(done)**
2. Add `pydantic-settings`, `openai`, `pytest`; add `app/config.py`. **(done)**
3. Copy provider config into `.env`; placeholders in `.env.example`. **(done)**
4. Uncomment `/api/chat`; add request/response models; echo last message; verify
   `POST /api/chat → 200`. **(done)**
5. `app/llm.py` client factory + one-shot smoke-test script. **(done)**

### Phase 2 — DCF math

6. `app/services/dcf.py`: pure functions — FCFF, growth fade, projection, terminal
   value, EV→equity→per-share.
7. `tests/test_dcf.py`: known values, `wacc <= g`, negative FCFF, zero shares.

### Phase 3 — EDGAR extraction (long pole)

8. `app/services/edgar.py`: ticker→CIK (cached `company_tickers.json`), submissions,
   `companyfacts`, annual-fact selection, raw cache in `data/raw/`.
9. `app/services/financials.py`: per-metric tag fallbacks, 5-year history, USD
   normalization, flags.
10. `tests/fixtures/{ticker}.json` + `tests/test_extraction.py` for all 9 tickers.

### Phase 4 — Pipeline + API

11. `app/services/valuation.py`: ticker → filing → history → assumptions → DCF.
12. `POST /api/analyze/{ticker}` (deterministic) and `/api/chat` (ticker + narrative).
13. API tests with `TestClient`; chat tested against a fake LLM.

### Phase 5 — UI

14. `frontend/src/lib/chat.ts`: `ValuationResult` types; `sendChat` returns
    `{ reply, valuation }`.
15. `ValuationCard`: history, assumptions, WACC, terminal value, EV, equity,
    per-share, flags, filing source.
16. `App.tsx`: render the card under the assistant message, ticker chips, error state;
    rebuild `frontend/dist`.

### Phase 6 — QA across the universe

17. Run all 9 tickers; record pass/fail/flags; fix tag fallbacks.
18. Add disclaimer (“not investment advice”), net-debt/share-count checks.

### Phase 7 — Submission

19. README, `assignments/day-36_capstone-kickoff/{README,VIDEO}.md`, PROGRESS 36–39,
    Feynman note, demo video.

## Anticipated blockers → unblock

| Blocker | Resolution |
|---|---|
| Provider 401 / base mismatch | One tiny completion; try parent `OPENAI_API_KEY` / `CLASS_API_KEY`; then ask for a valid pair. |
| Model unavailable on proxy | Probe model list; fallback `gpt-4o-mini`; record chosen model in config. |
| SEC 403 / rate limit | Descriptive `User-Agent` with contact; 150 ms delay; cache all responses. |
| Missing XBRL tag | Tag-fallback chain → per-ticker manual map → `422 missing_fields`. Never invent. |
| Multi-class shares (`GOOGL`, `META`) | Sum `dei:EntityCommonStockSharesOutstanding` across classes; flag. |
| Negative/volatile FCFF (`TSLA`, `AMZN`) | Latest positive or 3-year average; flag; assumption override. |
| Fiscal year differences | Select latest annual `10-K` facts by `end` / `fy`; label FY. |
| WACC market inputs | v1 manual defaults per ticker; CAPM later. |
| LLM invalid JSON | Pydantic validation + one repair retry; deterministic fallback. |
| Hallucinated numbers | Numbers never come from the model; it only formats computed JSON. |
| Prompt injection in filings | v1 sends structured facts only, not 10-K prose. |
| Chat payload growth | Cap to last N turns; full-history TODO remains. |
| Schema drift FE/BE | Pydantic/OpenAPI is the contract; mirror in `lib/chat.ts`; API tests. |

## Definition of Done

**Functional**

- Clean checkout: `uv sync`, `bun install`, documented `.env` → both dev servers run.
- All 9 allowlisted tickers return `200` from `/api/analyze/{ticker}` and a chat reply
  with a valuation card.
- Every result includes filing accession, FY end, and SEC URL.
- Missing required data returns `422` with `missing_fields`; no fabricated numbers.
- Same inputs → identical outputs (determinism test).

**Quality**

- `uv run pytest` green: DCF math, extraction fixtures for all 9 tickers, API tests.
- `bunx tsc --noEmit` and `bun run build` green.
- One live LLM smoke test passes.
- No secrets in git; `.env` ignored.

**UX**

- Chat accepts “value KO” or a bare ticker.
- Card renders in light/dark, works on mobile, links the source, shows a disclaimer.

**Submission**

- PROGRESS days 36–39 updated; day-36 assignment README + VIDEO; video recorded;
  conventional commits.

## Milestones

| Day | Deliverable |
|---|---|
| 36 | Phases 1–2: transport, config, DCF math |
| 37 | Phase 3: EDGAR for 3 tickers |
| 38 | Phase 3 for all 9 + Phase 4 pipeline |
| 39 | Phase 5 UI |
| 40 | Phase 6 QA + docs |
| 41 | Demo video |
| 42 | Submit |

## Open decisions

- Final WACC defaults per ticker (see spec).
- Whether v1 auto-fetches price/beta or stays manual (currently manual).
- Chat command syntax beyond “value \<ticker\>” (bare ticker supported).
