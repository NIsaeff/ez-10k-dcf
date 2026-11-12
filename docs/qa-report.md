# QA Report — 9-ticker DCF run

Date: 2026-11-12. Command: `uv run python -m scripts.analyze_all`.

| Ticker | FY | Value / share | Enterprise value | WACC | Flags |
|---|---|---|---|---|---|
| AAPL | 2026 | $123.14 | $1,856B | 8.0% | fcff_base_normalized, wacc_manual_default |
| MSFT | 2026 | $151.29 | $1,147B | 8.0% | fcff_base_normalized, wacc_manual_default |
| GOOGL | 2025 | $98.75 | $1,226B | 8.5% | fcff_base_normalized, wacc_manual_default |
| AMZN | 2025 | $27.70 | $282B | 9.0% | tax_rate_default, growth_default, fcff_base_normalized, wacc_manual_default |
| NVDA | 2026 | $50.86 | $1,245B | 9.5% | fcff_base_normalized, wacc_manual_default |
| META | 2025 | $55.82 | $167B | 9.0% | fcff_base_normalized, wacc_manual_default |
| TSLA | 2025 | $6.61 | $13B | 10.0% | fcff_base_normalized, wacc_manual_default |
| KO | 2025 | $31.70 | $172B | 7.5% | fcff_base_normalized, wacc_manual_default |
| PWR | 2025 | $249.19 | $43B | 9.0% | fcff_base_normalized, wacc_manual_default |

All 9 tickers return a deterministic result. The values are intentionally conservative
and are **not** price targets: WACC is a manual default, growth is a faded historical
FCFF CAGR, and the base is a normalized 5-year average. Some values sit well below
market prices — that is the model's assumption set, not a claim about intrinsic value.

## Notes / known limitations

- **WACC is manual** per ticker (`wacc_manual_default`). CAPM/auto market data is a
  later rung.
- **FCFF base is normalized** to avoid one capex/working-capital spike dominating the
  valuation (`fcff_base_normalized`). This is why KO/GOOGL results are not distorted by
  their 2025 working-capital swings.
- **AMZN** hits `tax_rate_default` (a negative pretax year in the window) and
  `growth_default`; treat its value as a coarse estimate.
- **TSLA** has volatile/negative FCFF years; the normalized positive base produces a
  low value. The flag list is the honest signal.
- **Debt** uses the best available XBRL total; `debt_partial` appears only when the
  fallback component sum was needed. Commercial paper / short-term borrowings are added
  when present.
- Raw SEC payloads are cached under `data/raw/` and gitignored. Tests run from trimmed
  fixtures in `tests/fixtures/`; no network in tests.
- **LLM narration** is non-deterministic prose around deterministic numbers. If the
  provider fails, a formatted template is used.
- UI verified in Chromium via the `opencode-chromium` MCP: “value KO” renders the
  valuation card with per-share, EV, WACC, history table, flags, and SEC source link.

## Test coverage

- `uv run pytest -q` → 34 passed.
- `uvx ruff check app scripts tests` → clean.
- `cd frontend && bunx tsc --noEmit` → clean.
- `bun run build` → passes; FastAPI serves `frontend/dist`.
