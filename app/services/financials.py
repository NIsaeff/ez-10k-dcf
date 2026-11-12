"""Map SEC companyfacts XBRL into raw annual financial rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.schemas import FilingInfo
from app.services import edgar

METRIC_TAGS: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ],
    "ebit": ["OperatingIncomeLoss"],
    "pretax_income": [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    ],
    "tax_expense": [
        "IncomeTaxExpenseBenefit",
        "IncomeTaxExpenseBenefitContinuingOperations",
    ],
    "depreciation_amortization": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "DepreciationAndAmortization",
        "Depreciation",
    ],
    "capital_expenditures": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PaymentsForCapitalImprovements",
    ],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
}

SHARE_TAGS = [
    "WeightedAverageNumberOfDilutedSharesOutstanding",
    "WeightedAverageNumberOfSharesOutstandingBasic",
]


class InsufficientData(Exception):
    def __init__(self, ticker: str, missing_fields: list[str]):
        self.ticker = ticker
        self.missing_fields = missing_fields
        super().__init__(f"Insufficient data for {ticker}: {', '.join(missing_fields)}")


@dataclass
class CompanyFinancials:
    ticker: str
    company_name: str
    cik: str
    filing: FilingInfo
    raw_years: list[dict[str, Any]]
    total_debt: float
    cash_and_equivalents: float
    shares_outstanding: float
    share_count_source: str
    flags: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


def _debt_series(gaap: dict[str, Any], flags: list[str]) -> dict[int, float]:
    _total_tag, total = edgar.best_series(
        gaap,
        [
            "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities",
            "DebtLongtermAndShorttermCombinedAmount",
            "LongTermDebt",
        ],
    )
    if not total:
        flags.append("debt_partial")
        noncurrent = edgar.annual_series(gaap, "LongTermDebtNoncurrent")
        current = edgar.annual_series(gaap, "LongTermDebtCurrent")
        short_term = edgar.annual_series(gaap, "ShortTermBorrowings")
        years = sorted(set(noncurrent) | set(current) | set(short_term))
        total = {
            year: (noncurrent.get(year) or 0.0)
            + (current.get(year) or 0.0)
            + (short_term.get(year) or 0.0)
            for year in years
        }

    # Commercial paper / short-term borrowings are usually outside the long-term
    # debt total, so add them when present.
    extra_tags = ["CommercialPaper", "ShortTermBorrowings"]
    extra: dict[int, float] = {}
    for tag in extra_tags:
        for year, value in edgar.annual_series(gaap, tag).items():
            extra[year] = extra.get(year, 0.0) + value
    for year, value in extra.items():
        if year in total:
            total[year] += value

    return total


def _share_series(gaap: dict[str, Any], dei: dict[str, Any]) -> tuple[str, dict[int, float]]:
    tag, values = edgar.best_series(gaap, SHARE_TAGS, unit="shares")
    if values:
        return tag or "unknown", values
    dei_values = edgar.annual_series(dei, "EntityCommonStockSharesOutstanding", unit="shares")
    if dei_values:
        return "dei:EntityCommonStockSharesOutstanding", dei_values
    return "missing", {}


def build_from_facts(
    *,
    ticker: str,
    company_name: str,
    cik: str,
    filing: FilingInfo,
    facts: dict[str, Any],
) -> CompanyFinancials:
    gaap = facts.get("facts", {}).get("us-gaap", {})
    dei = facts.get("facts", {}).get("dei", {})
    flags: list[str] = []

    series: dict[str, dict[int, float]] = {}
    for metric, tags in METRIC_TAGS.items():
        tag, values = edgar.best_series(gaap, tags)
        series[metric] = values
        if not values and metric == "revenue":
            flags.append("revenue_missing")
        _ = tag

    debt = _debt_series(gaap, flags)
    share_source, shares = _share_series(gaap, dei)

    years = sorted(
        set(series["ebit"])
        & set(series["depreciation_amortization"])
        & set(series["capital_expenditures"])
    )[-5:]
    if not years:
        raise InsufficientData(
            ticker,
            ["ebit", "depreciation_amortization", "capital_expenditures"],
        )

    raw_years: list[dict[str, Any]] = []
    for year in years:
        raw_years.append(
            {
                "fiscal_year": year,
                "revenue": series["revenue"].get(year),
                "ebit": series["ebit"].get(year),
                "pretax_income": series["pretax_income"].get(year),
                "tax_expense": series["tax_expense"].get(year),
                "depreciation_amortization": series["depreciation_amortization"].get(year),
                "capital_expenditures": series["capital_expenditures"].get(year),
                "current_assets": series["current_assets"].get(year),
                "current_liabilities": series["current_liabilities"].get(year),
            }
        )

    latest_year = years[-1]
    latest_debt = debt.get(latest_year)
    latest_cash = series["cash"].get(latest_year)
    latest_shares = shares.get(latest_year)

    missing: list[str] = []
    if latest_debt is None:
        missing.append("total_debt")
    if latest_cash is None:
        missing.append("cash_and_equivalents")
    if latest_shares is None or latest_shares <= 0:
        missing.append("shares_outstanding")
    if missing:
        raise InsufficientData(ticker, missing)

    if share_source == "dei:EntityCommonStockSharesOutstanding":
        flags.append("shares_from_dei")
    elif share_source != "WeightedAverageNumberOfDilutedSharesOutstanding":
        flags.append("shares_from_basic")

    sources = [
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:0>10}.json",
        filing.url,
    ]

    return CompanyFinancials(
        ticker=ticker,
        company_name=company_name,
        cik=cik,
        filing=filing,
        raw_years=raw_years,
        total_debt=float(latest_debt),
        cash_and_equivalents=float(latest_cash),
        shares_outstanding=float(latest_shares),
        share_count_source=share_source,
        flags=flags,
        sources=sources,
    )


def load_company(ticker: str) -> CompanyFinancials:
    info = edgar.company_info(ticker)
    cik = int(info["cik"])
    filing = FilingInfo(**edgar.latest_10k(cik))
    facts = edgar.companyfacts(cik)
    return build_from_facts(
        ticker=ticker.upper(),
        company_name=str(info["title"]),
        cik=f"{cik:010d}",
        filing=filing,
        facts=facts,
    )
