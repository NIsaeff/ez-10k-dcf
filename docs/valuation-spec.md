# EZ-10k — Valuation Spec (v0.1)

Status: **frozen for v1**. Any change to formulas, tags, or schema updates this file
and its tests together. See [`capstone-plan.md`](capstone-plan.md).

## Scope

Supported tickers: `AAPL`, `MSFT`, `GOOGL`, `AMZN`, `NVDA`, `META`, `TSLA`, `KO`,
`PWR`. Anything else → `422 unsupported_ticker`.

One company per request. No comparables, no portfolio, no persistence.

## API contract

### `POST /api/analyze/{ticker}`

Deterministic valuation. Path ticker must be in the allowlist (case-insensitive).

- `200` → `ValuationResult`
- `422` → `{ "error": "unsupported_ticker" | "insufficient_data", "ticker": "...", "missing_fields": [...] }`
- `502` → upstream SEC failure after retries

### `POST /api/chat`

```json
{ "messages": [{ "role": "user", "content": "value KO" }] }
```

Response:

```json
{ "reply": "...", "valuation": { /* ValuationResult or null */ } }
```

Ticker detection: last user message, first allowlisted token (word-boundary match).
No ticker → normal chat. Ticker → call the analyzer and have the model **format** the
result; the model never invents or edits numbers.

## `ValuationResult`

All money in **USD (not millions)**. Shares in units. Rates as decimals.
`history` ascending, max 5 fiscal years. `projection` starts at the year after the
latest fiscal year.

```jsonc
{
  "ticker": "KO",
  "company_name": "The Coca-Cola Company",
  "cik": "0000021344",
  "filing": {
    "accession_number": "0000021344-25-000011",
    "form": "10-K",
    "fiscal_year_end": "2024-12-31",
    "filed": "2025-02-20",
    "url": "https://www.sec.gov/Archives/edgar/data/21344/..."
  },
  "history": [
    {
      "fiscal_year": 2020,
      "revenue": 33014000000,
      "ebit": 10394000000,
      "pretax_income": 9804000000,
      "tax_expense": 1942000000,
      "depreciation_amortization": 1075000000,
      "capital_expenditures": 1247000000,
      "change_in_nwc": -120000000,
      "fcff": 8230000000
    }
  ],
  "assumptions": {
    "projection_years": 5,
    "terminal_growth_rate": 0.025,
    "wacc": 0.075,
    "wacc_source": "manual_default",
    "tax_rate": 0.198,
    "tax_rate_source": "effective_from_filing",
    "growth_rate": 0.04,
    "growth_source": "historical_fcff_cagr",
    "fcff_base": 8230000000,
    "fcff_base_source": "latest_positive",
    "share_count_source": "diluted_weighted_average",
    "net_debt_treatment": "total_debt_minus_cash"
  },
  "projection": [
    { "year": 2025, "fcff": 8560000000, "discount_factor": 0.9302, "present_value": 7963000000 }
  ],
  "valuation": {
    "terminal_value": 163000000000,
    "present_value_terminal": 113000000000,
    "enterprise_value": 152000000000,
    "total_debt": 42000000000,
    "cash_and_equivalents": 16000000000,
    "net_debt": 26000000000,
    "equity_value": 126000000000,
    "shares_outstanding": 4310000000,
    "value_per_share": 29.23
  },
  "flags": ["nwc_unavailable"],
  "sources": [
    "https://data.sec.gov/api/xbrl/companyfacts/CIK0000021344.json",
    "https://www.sec.gov/Archives/edgar/data/21344/..."
  ],
  "disclaimer": "Illustrative valuation, not investment advice."
}
```

Validation rules:

- `wacc > terminal_growth_rate`, else `422`.
- `shares_outstanding > 0`, else `422`.
- `value_per_share >= 0`; negative equity is allowed but flagged `negative_equity`.
- Rates rounded to 4 decimals, per-share to 2, display only; keep full floats internally.

## Formulas

### 1. Tax rate

```
tax_rate = clamp(tax_expense / pretax_income, 0, 0.35)
```

If `pretax_income <= 0` or either input is missing: `tax_rate = 0.21`,
flag `tax_rate_default`.

### 2. Historical FCFF (per fiscal year)

```
fcff = ebit * (1 - tax_rate) + depreciation_amortization
       - capital_expenditures - change_in_nwc
```

`change_in_nwc = nwc_t - nwc_{t-1}` where `nwc = current_assets - current_liabilities`.
Missing NWC → `0`, flag `nwc_unavailable` (first year always has no delta).
A working-capital release (negative delta) increases FCFF.

### 3. Growth

```
g_hist = (fcff_latest / fcff_oldest) ** (1 / (n - 1)) - 1
g_hist = clamp(g_hist, -0.20, 0.30)
```

If `n < 3`, `fcff_oldest <= 0`, or the result is undefined: `g_hist = 0.05`,
flag `growth_default`.

Projection fades linearly from `g_hist` in year 1 to `terminal_growth_rate` in year N:

```
g_i = g_hist + (terminal_growth_rate - g_hist) * (i - 1) / (N - 1)
```

### 4. FCFF base and projection

`fcff_base` = latest FCFF if positive, else the mean of positive years in the last 3,
else latest FCFF. Default path flags `fcff_base_3yr_avg` when averaged; negative base
flags `negative_fcff`.

```
fcff_1 = fcff_base * (1 + g_1)
fcff_i = fcff_{i-1} * (1 + g_i)
```

### 5. Terminal value and discounting

```
fcff_{N+1} = fcff_N * (1 + terminal_growth_rate)
terminal_value = fcff_{N+1} / (wacc - terminal_growth_rate)   # Gordon growth
present_value_terminal = terminal_value / (1 + wacc) ** N
present_value_i = fcff_i / (1 + wacc) ** i
enterprise_value = sum(present_value_i) + present_value_terminal
```

### 6. Equity and per-share

```
net_debt = total_debt - cash_and_equivalents
equity_value = enterprise_value - net_debt
value_per_share = equity_value / shares_outstanding
```

Total debt = `LongTermDebtNoncurrent + LongTermDebtCurrent + ShortTermBorrowings`;
fallback `LongTermDebt + DebtCurrent`. Partial debt data → flag `debt_partial`.

Cash = `CashAndCashEquivalentsAtCarryingValue`; fallback
`CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents`.

## WACC (v1)

Manual defaults, overridable per request; the card always displays the value and
source. No live beta/price feed in v1.

| Ticker | WACC |
|---|---|
| `KO` | 7.5% |
| `AAPL`, `MSFT` | 8.0% |
| `GOOGL` | 8.5% |
| `AMZN`, `META`, `PWR` | 9.0% |
| `NVDA` | 9.5% |
| `TSLA` | 10.0% |

Defaults are starting assumptions, not investment judgments. CAPM/auto market data is
a later rung; when added, set `wacc_source = "capm"`.

## EDGAR data mapping

Source: SEC `companyfacts` XBRL, annual facts only (`form = "10-K"`, `fp = "FY"`,
latest `fy` by `end` date, `units.USD` / `units.shares`).

| Metric | Tag fallback order |
|---|---|
| Revenue | `RevenueFromContractWithCustomerExcludingAssessedTax`, `Revenues`, `SalesRevenueNet`, `RevenueFromContractWithCustomerIncludingAssessedTax` |
| EBIT | `OperatingIncomeLoss` |
| Pretax income | `IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest`, `IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments` |
| Tax expense | `IncomeTaxExpenseBenefit`, `IncomeTaxExpenseBenefitContinuingOperations` |
| D&A | `DepreciationDepletionAndAmortization`, `DepreciationAmortizationAndAccretionNet`, `DepreciationAndAmortization`, `Depreciation` |
| CapEx | `PaymentsToAcquirePropertyPlantAndEquipment`, `PaymentsToAcquireProductiveAssets`, `PaymentsForCapitalImprovements` |
| Current assets | `AssetsCurrent` |
| Current liabilities | `LiabilitiesCurrent` |
| Long-term debt | `LongTermDebtNoncurrent`, `LongTermDebt` |
| Current debt | `LongTermDebtCurrent`, `DebtCurrent`, `ShortTermBorrowings`, `ShortTermDebt` |
| Cash | `CashAndCashEquivalentsAtCarryingValue`, `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents` |
| Shares | `WeightedAverageNumberOfDilutedSharesOutstanding`, `WeightedAverageNumberOfSharesOutstandingBasic`, `dei:EntityCommonStockSharesOutstanding` |

Multi-class shares (`GOOGL`, `META`): sum `dei:EntityCommonStockSharesOutstanding`
across classes; flag `multi_class_shares`.

Filing selection: latest `10-K` from `submissions` by `filingDate`; use its
`accessionNumber`, `reportDate` (FY end), and archive URL.

Caching: raw `company_tickers.json` and `companyfacts` responses go to `data/raw/`
(gitignored). Tests use checked-in fixtures under `tests/fixtures/`.

## Missing-data policy

**Required:** latest annual 10-K, `ebit`, D&A, CapEx, shares, cash, total debt,
`wacc > terminal_growth_rate`. Missing → `422 insufficient_data` with
`missing_fields`.

**Optional:** revenue, pretax income, NWC. Missing → flag + documented fallback.
The API never fabricates a figure; flags are part of the response.

## Determinism

Given the same filing facts and assumptions, output is byte-identical. All math is
pure Python (no LLM, no network) and covered by tests. The LLM receives the finished
`ValuationResult` and only writes prose around it.

## Flags

`tax_rate_default`, `nwc_unavailable`, `growth_default`, `fcff_base_3yr_avg`,
`negative_fcff`, `multi_class_shares`, `shares_from_dei`, `debt_partial`,
`revenue_missing`, `history_lt_3y`, `wacc_manual_default`, `negative_equity`.

## Open questions

- Final WACC values above are placeholders; confirm after the first 9-ticker run.
- Whether to include short-term investments in cash (currently excluded).
- Whether v1 includes a sensitivity table (currently no).
