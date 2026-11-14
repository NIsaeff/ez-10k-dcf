"""Orchestrate ticker -> SEC facts -> FCFF history -> DCF valuation.

The engine accepts assumption overrides so the wizard and the chat share one
implementation: ``engine`` in the response is exactly what the projection math
consumed, and the frontend mirrors those numbers for slider previews.
"""

from __future__ import annotations

from app.schemas import (
    Assumptions,
    DcfOverrides,
    EngineInputs,
    SourceFact,
    ValuationResult,
)
from app.services import dcf, financials, macro

SUPPORTED_TICKERS = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "NVDA",
    "META",
    "TSLA",
    "KO",
    "PWR",
]

WACC_DEFAULTS = {
    "KO": 0.075,
    "AAPL": 0.080,
    "MSFT": 0.080,
    "GOOGL": 0.085,
    "AMZN": 0.090,
    "META": 0.090,
    "PWR": 0.090,
    "NVDA": 0.095,
    "TSLA": 0.100,
}

# Fallback for tickers outside the pilot list (wizard accepts any SEC filer).
GENERIC_WACC = 0.09

TERMINAL_GROWTH = 0.025
PROJECTION_YEARS = 5
DISCLAIMER = "Illustrative valuation for a class project. Not investment advice."


class UnsupportedTicker(Exception):
    def __init__(self, ticker: str):
        self.ticker = ticker
        super().__init__(f"Unsupported ticker: {ticker}")


class InvalidAssumptions(Exception):
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


def analyze(
    ticker: str,
    overrides: DcfOverrides | None = None,
    *,
    allow_any: bool = False,
) -> ValuationResult:
    """Value a ticker.

    ``allow_any`` lets the wizard value any ticker SEC knows about; the chat
    keeps the small pilot allowlist so replies stay predictable.
    """
    ticker = ticker.upper().strip()
    if not allow_any and ticker not in SUPPORTED_TICKERS:
        raise UnsupportedTicker(ticker)

    try:
        company = financials.load_company(ticker)
    except KeyError as exc:
        raise UnsupportedTicker(ticker) from exc

    return analyze_from_company(company, overrides)


def analyze_from_company(
    company: financials.CompanyFinancials,
    overrides: DcfOverrides | None = None,
) -> ValuationResult:
    ticker = company.ticker

    history, history_flags = dcf.build_history(company.raw_years)
    if not history:
        raise financials.InsufficientData(
            ticker,
            ["ebit", "depreciation_amortization", "capital_expenditures"],
        )

    base_fcff, base_source, base_flags = dcf.select_fcff_base(history)
    growth, growth_source, growth_flags = dcf.historical_growth(history, base_fcff)

    latest = history[-1]
    latest_raw = company.raw_years[-1]
    tax_rate, tax_default = dcf.effective_tax_rate(
        latest_raw.get("tax_expense"), latest_raw.get("pretax_income")
    )

    # Effective assumptions: engine defaults, then any user overrides.
    years = PROJECTION_YEARS
    terminal_growth = TERMINAL_GROWTH
    growth_model = "fade"
    wacc = WACC_DEFAULTS.get(ticker, GENERIC_WACC)
    wacc_source = "manual_default"
    applied: list[str] = []

    if overrides is not None:
        if overrides.projection_years is not None:
            years = overrides.projection_years
            applied.append("projection_years")
        if overrides.terminal_growth_rate is not None:
            terminal_growth = overrides.terminal_growth_rate
            applied.append("terminal_growth_rate")
        if overrides.growth_model is not None:
            growth_model = overrides.growth_model
            applied.append("growth_model")
        if overrides.growth_rate is not None:
            growth = overrides.growth_rate
            growth_source = "override"
            applied.append("growth_rate")
        if overrides.wacc is not None:
            wacc = overrides.wacc
            wacc_source = "override"
            applied.append("wacc")

    if wacc <= terminal_growth:
        raise InvalidAssumptions(
            f"WACC ({wacc:.2%}) must be greater than terminal growth "
            f"({terminal_growth:.2%})"
        )
    if wacc <= -1.0:
        raise InvalidAssumptions("WACC must be greater than -100%")

    projection = dcf.project_fcff(
        base_fcff=base_fcff,
        growth_rate=growth,
        terminal_growth_rate=terminal_growth,
        base_year=latest.fiscal_year,
        wacc=wacc,
        years=years,
        growth_model=growth_model,
    )
    summary, valuation_flags = dcf.build_valuation(
        projection=projection,
        terminal_growth_rate=terminal_growth,
        wacc=wacc,
        total_debt=company.total_debt,
        cash_and_equivalents=company.cash_and_equivalents,
        shares_outstanding=company.shares_outstanding,
    )

    flags = list(
        dict.fromkeys(
            [
                *company.flags,
                *history_flags,
                *growth_flags,
                *base_flags,
                *valuation_flags,
                *([] if wacc_source == "override" else ["wacc_manual_default"]),
                *([] if ticker in WACC_DEFAULTS else ["wacc_generic_default"]),
            ]
        )
    )

    assumptions = Assumptions(
        projection_years=years,
        terminal_growth_rate=terminal_growth,
        wacc=wacc,
        wacc_source=wacc_source,
        tax_rate=tax_rate,
        tax_rate_source="default" if tax_default else "effective_from_filing",
        growth_rate=growth,
        growth_model=growth_model,
        growth_source=growth_source,
        fcff_base=base_fcff,
        fcff_base_source=base_source,
        share_count_source=company.share_count_source,
        net_debt_treatment="total_debt_minus_cash",
    )

    engine = EngineInputs(
        base_fcff=base_fcff,
        growth_rate=growth,
        growth_model=growth_model,
        terminal_growth_rate=terminal_growth,
        projection_years=years,
        wacc=wacc,
        base_wacc=WACC_DEFAULTS.get(ticker, GENERIC_WACC),
        total_debt=company.total_debt,
        cash=company.cash_and_equivalents,
        shares_outstanding=company.shares_outstanding,
        tax_rate=tax_rate,
        base_year=latest.fiscal_year,
    )

    return ValuationResult(
        ticker=ticker,
        company_name=company.company_name,
        cik=company.cik,
        filing=company.filing,
        history=history,
        assumptions=assumptions,
        projection=projection,
        valuation=summary,
        engine=engine,
        overrides_applied=applied,
        flags=flags,
        sources=company.sources,
        source_facts=[SourceFact(**row) for row in company.source_facts],
        macro=macro.snapshot(),
        disclaimer=DISCLAIMER,
    )
