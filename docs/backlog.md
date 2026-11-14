# Backlog

Open work that is understood but not scheduled. Newest first. Each item should be
actionable without re-reading the conversation that produced it.

---

## Any-ticker DCF with typed incompatibility feedback

**Status:** not started · **Area:** engine + wizard · **Captured:** 2026-11-14

### Goal

Let a user pick **any** ticker in the SEC EDGAR universe and have the app attempt
the FCFF → DCF workflow. When a company's input shape can't support that model,
stop with a **specific, typed error or warning** instead of a generic failure or,
worse, a plausible-looking wrong number.

Today the wizard accepts any SEC ticker (`allow_any=True`) but expresses every
problem as one of two outcomes: a valuation, or `422 insufficient_data` with a
field list. Silent wrong answers are possible.

### Evidence (probe run 2026-11-14)

63 tickers — 31 large caps, 10 edge cases, 22 random from
`company_tickers.json` (seed 7), cached under `/tmp` — through the current
pipeline:

```
ok 30 · insufficient 17 · no 10-K 13 · not in ticker map 3
```

Of the 30 "ok", three returned HTTP 200 with unusable numbers:

| Ticker | Result | Cause |
|---|---|---|
| MCD | $142,470,412/share | Diluted shares tagged as `708.3` (millions), not `708,300,000`; no sanity check |
| GS | $5,354.96/share | Broker-dealer; FCFF doesn't apply, revenue missing, EBIT synthesized |
| C | $236.29/share | Bank; FCFF doesn't apply |

Two anomalies to chase separately:

- `GOOGL`/`GOOG` return only 3 years of history while sharing CIK 1652044
  (12.23B shares is correct — they share one diluted figure).
- `XOM` now maps to CIK 2115436 *ExxonMobil Holdings Corp*, which files 10-Qs but
  no 10-K yet. Needs either a predecessor-CIK fallback or a truthful
  "no annual report yet for this registrant" error.

### Failure taxonomy

| Class | Examples | Deterministic fix available |
|---|---|---|
| Universe ≠ companies | `QQQ`/`VOO`/`ARKK` absent from the map; `SPY` has a CIK but no 10-K; `NLY-PF`, `MMTXW`, `FMACR`, `BABYF` are preferreds/warrants/units/OTC F-shares | Security-type gate |
| Model doesn't apply | JPM/BAC (banks), GS (broker), BRK-B (insurer), O/SPG/NLY (REITs), SPACs | SIC gate — `submissions.sic` is present: 6021 banks, 6211 brokers, 6798 REITs, 6331 insurers |
| Tag staleness / drift | PG & COST `LongTermDebt` ends 2015 while `LongTermDebtNoncurrent` covers 2026; LLY & NKE missing EBIT; JNJ (already handled via derivation) | Coverage-first recipe selection |
| Scale / unit / period errors | MCD shares in millions; NKE tags a FY2026 filing as `fy=2027` | Cross-check + plausibility bounds |
| Entity plumbing | XOM → new holding company with no 10-K; V has no usable share tag; BRK-B `dei` is stale | Predecessor lookup, better errors |

### Proposed approach

1. **Applicability gate** (before any math). SIC + statement shape →
   `operating_nonfinancial` | `bank` | `insurer` | `reit` | `fund` | `spac` |
   `foreign_private_issuer` | `unknown`. Only the first runs FCFF; the rest return
   `422 not_applicable` with the reason. Removes the dangerous answers.
2. **Recipe engine per metric.** Replace "first tag that exists" with ordered
   recipes that yield `year → value` plus provenance:
   - `ebit`: `OperatingIncomeLoss` → `pretax + interest` → `revenue − costs`
   - `total_debt`: primary tag → per-year composite (`Noncurrent + Current +
     ShortTerm + CommercialPaper`) → merged
   - `shares`: diluted weighted → basic → `dei` summed across classes, then
     plausibility-checked
   Selection rule: best **coverage of the projection window**, preferring exact
   tags. Fixes PG, COST, LLY, NKE, MCD, V at once.
3. **Coverage contract.** Emit per-metric, per-year status (`exact` / `derived` /
   `missing`); refuse below 3 consecutive complete years instead of collapsing
   everything into one `missing_fields` list.
4. **Plausibility guards.** Deterministic bounds that downgrade or refuse:
   shares within 0.5–2× `dei`; capex/revenue 0–40%; |FCFF|/revenue < 60%; YoY FCFF
   jump > 5× (KO 2024→2025); terminal value > 85% of EV; shares change > 20% YoY;
   effective tax outside 0–35%.
5. **Confidence field.** `confidence: high | medium | low` with reasons, surfaced
   in the wizard's flag row and the API.

### Acceptance criteria

- No ticker returns a valuation whose share count is implausible (MCD regression
  test).
- Banks, insurers, REITs, funds and SPACs return `not_applicable` with a reason,
  never a number.
- Preferred/warrant/unit tickers are rejected or explicitly labelled as the
  parent's common equity.
- Every valuation states which recipe produced each input and a confidence level.
- A corpus harness runs N≥200 random tickers and reports success/failure by
  class, so improvements are measurable.

### Open decisions

- Breadth with refusals vs depth on the 9-ticker pilot list — different products.
- Is a `low_confidence` number acceptable, or should anything suspicious refuse?
- Keep the chat allowlist while the wizard goes broad? (Recommendation: yes.)

### Out of scope for the first pass

Per-industry models (DDM/FCFE for banks, FFO/AFFO for REITs, embedded value for
insurers), IFRS/20-F support, and security-level (preferred series) valuation.

### Suggested sequence

Corpus harness (2–3 days) → applicability gate (2 days) → recipe engine + coverage
(1–1.5 weeks) → guards + confidence (2–3 days) → per-industry models.
