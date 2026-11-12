"""Orchestrate ticker -> SEC facts -> FCFF history -> DCF valuation."""

from __future__ import annotations

from app.schemas import Assumptions, SourceFact, ValuationResult
from app.services import dcf, financials

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

TERMINAL_GROWTH = 0.025
PROJECTION_YEARS = 5
DISCLAIMER = "Illustrative valuation for a class project. Not investment advice."


class UnsupportedTicker(Exception):
    def __init__(self, ticker: str):
        self.ticker = ticker
        super().__init__(f"Unsupported ticker: {ticker}")


def analyze(ticker: str) -> ValuationResult:
    ticker = ticker.upper().strip()
    if ticker not in SUPPORTED_TICKERS:
        raise UnsupportedTicker(ticker)
    return analyze_from_company(financials.load_company(ticker))


def analyze_from_company(company: financials.CompanyFinancials) -> ValuationResult:
    ticker = company.ticker
    if ticker not in SUPPORTED_TICKERS:
        raise UnsupportedTicker(ticker)

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

    wacc = WACC_DEFAULTS[ticker]
    projection = dcf.project_fcff(
        base_fcff=base_fcff,
        growth_rate=growth,
        terminal_growth_rate=TERMINAL_GROWTH,
        base_year=latest.fiscal_year,
        wacc=wacc,
        years=PROJECTION_YEARS,
    )
    summary, valuation_flags = dcf.build_valuation(
        projection=projection,
        terminal_growth_rate=TERMINAL_GROWTH,
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
                "wacc_manual_default",
            ]
        )
    )

    assumptions = Assumptions(
        projection_years=PROJECTION_YEARS,
        terminal_growth_rate=TERMINAL_GROWTH,
        wacc=wacc,
        wacc_source="manual_default",
        tax_rate=tax_rate,
        tax_rate_source="default" if tax_default else "effective_from_filing",
        growth_rate=growth,
        growth_source=growth_source,
        fcff_base=base_fcff,
        fcff_base_source=base_source,
        share_count_source=company.share_count_source,
        net_debt_treatment="total_debt_minus_cash",
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
        flags=flags,
        sources=company.sources,
        source_facts=[SourceFact(**row) for row in company.source_facts],
        disclaimer=DISCLAIMER,
    )
