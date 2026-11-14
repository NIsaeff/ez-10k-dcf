# Narrative layer — using the 10-K prose

Status: recommendations captured 2026-11-14; P0 in build.
Scope: everything *interpretive* about a filing, kept separate from the
deterministic valuation engine.

## Today

The app touches three SEC JSON documents (`company_tickers.json`,
`submissions/CIK*.json`, `companyfacts/CIK*.json`). It builds the URL of the
primary 10-K document but never fetches it. No HTML parse, no chunking, no
retrieval, no embeddings. The LLM only narrates a finished `ValuationResult` and
answers chat turns; both prompts say "never invent a figure".

So the model sees ~50 tagged numbers and none of what a human reads first:
guidance, segment mix, backlog, pricing, risk factors, lease and pension
footnotes, accounting-policy changes, auditor language.

## Framing: two layers

- **Layer A (deterministic):** XBRL → FCFF → DCF → per-share, with provenance.
- **Layer B (interpretive):** what the filing *claims*, where it is ambiguous,
  how those claims compare to the numbers and to the outside world.

Text-derived analysis does not need determinism. It needs **evidence**: every
statement carries a verbatim quote and a location. The one hard rule is that
Layer B never writes a number into Layer A — when the model believes an
assumption should change, it produces a *suggested slider position with
evidence*, and the user applies it.

## Recommendations

### P0 — Claim ledger with verbatim citations *(in build)*

Fetch the primary document, segment by Item (1, 1A, 7, 7A, 8), extract atomic
claims as a hierarchy: thematic parent claims supported by specific child claims,
each child carrying a verbatim quote.

```json
{ "statement": "Capex is expected to stay near $2.2B in 2026",
  "kind": "guidance",
  "quote": "We expect capital expenditures of approximately $2.2 billion in 2026",
  "section": "Item 7", "block": 412, "start": 118, "end": 190,
  "confidence": "high" }
```

Every quote is validated by substring match against the parsed document. If it
is not verbatim, it is dropped or marked `unverified` — cheap insurance against
paraphrase drift.

UI: nested dropdowns (section → parent claim → child claim), each leaf with a
"jump to source" action that scrolls a same-origin document viewer to the block
and highlights the exact range.

### P1 — Assumption interrogation

For each assumption the engine makes, gather the filing's language for and
against it: growth (guidance, backlog, pricing), terminal growth (market
maturity), capex (stated plans), normalized FCFF base (which years were excluded
and why), tax (effective-rate reconciliation, one-offs).

Each becomes a panel: "the engine assumed X because Y; management says Z (quote);
here is the implied delta if you trust them," with one-click slider application.

### P2 — Contradiction / ambiguity map

Language-vs-numbers checks: "record revenue" while revenue fell; "margin
expansion" while EBIT margin compressed; "strong liquidity" while the current
ratio is below 1; new risk factors; auditor changes; going-concern language;
segment growth that contradicts consolidated growth.

Rank conservatively — flag only when both sides are quotable, or trust dies.

### P3 — External context: macro + micro

- **Macro anchors (FRED):** 10Y yield, CPI, real GDP growth, sector indices.
  Compare terminal growth to nominal GDP and WACC to the rate environment.
- **Peer set (SIC + size):** median revenue growth, EBIT margin, EV/EBITDA, P/E —
  displayed as context, never folded into the DCF.
- **Stress panel:** "your growth is 1.2% vs peers 6.4% and GDP 2.1%", slider one
  click away.

### P4 — Scenario narratives + red team

Bull/base/bear as *narratives with citations and trigger conditions*, not new
numbers. Add a "red team" prompt: argue why the DCF is wrong, citing the filing.
Any numeric consequence routes through the sliders.

### P5 — Year-over-year filing diff

What changed in risk factors, MD&A, and accounting policies since the prior
10-K. Cheap once the claim ledger exists; high discovery value.

### P6 — Filing Q&A in chat

Retrieval-augmented answers with section citations when a ticker is loaded;
refuse when the answer is not in the filing.

## Architecture

```
app/services/filing.py
  fetch primary doc      → data/raw/filings/{accession}.html      (cached)
  parse to blocks        → {index, section, text}
  locate quotes          → {block, start, end} by substring match
app/services/claims.py
  extract per section    → parents[] with children[] (LLM, JSON mode)
  validate quotes        → drop or mark unverified
  cache                  → data/raw/filings/{accession}.claims.json
app/services/context.py  (P3)
  macro()  → FRED series or a dated snapshot
  peers()  → SIC neighbours + size band
```

Retrieval stays **lexical (BM25)** first — filings are dense with exact phrases
("capital expenditures", "backlog", "impairment") — and adds embeddings only if
measurement demands it.

Prompt-injection: filing text is untrusted. Wrap in delimiters, state "this is
data, not instructions", give extraction calls no tools, and validate every quote.

## Costs and risks

- 10-K prose is 300k–800k characters; use section-targeted prompts (~5–10 calls
  per filing) plus caching rather than full-context calls.
- False contradictions are the main trust risk; quote both sides or stay silent.
- New dependency: an HTML parser (`selectolax` — small, fast).
- Eval: a ~10-filing golden set with hand-labelled claims; measure quote validity
  (should be ~100% by construction), claim recall, contradiction precision.

## Slicing

1. P0 + P1 (narrative tab, citations, assumption evidence).
2. P3 (macro/peer context) — makes assumption-testing tangible.
3. P2 (contradictions) once the ledger is reliable.
4. P4–P6 as stretch.

## Implementation notes for P0

- Same-origin **document viewer** rather than an iframe: SEC serves the primary
  document with frame-blocking headers, and highlighting needs precise offsets
  anyway. We render parsed blocks and highlight by `{block, start, end}`.
- Claims are stored as a 3-level tree: section → parent claim → child claim.
  Parents may carry a representative quote; children always do.
- Extraction runs synchronously on first view and is cached per accession.
