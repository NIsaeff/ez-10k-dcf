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
    source_facts: list[dict[str, Any]] = field(default_factory=list)


DebtComponents = list[tuple[str, dict[int, dict[str, Any]]]]


def _debt_series(
    gaap: dict[str, Any], flags: list[str]
) -> tuple[dict[int, float], DebtComponents]:
    """Total debt by fiscal year plus the tags/facts behind it."""
    primary_tag, primary_facts = edgar.best_facts(
        gaap,
        [
            "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities",
            "DebtLongtermAndShorttermCombinedAmount",
            "LongTermDebt",
        ],
    )
    components: DebtComponents = []

    if primary_facts:
        total = {year: float(row["val"]) for year, row in primary_facts.items()}
        components.append((primary_tag or "unknown", primary_facts))
        extra_tags = ["CommercialPaper", "ShortTermBorrowings"]
    else:
        flags.append("debt_partial")
        for tag in ("LongTermDebtNoncurrent", "LongTermDebtCurrent", "ShortTermBorrowings"):
            facts = edgar.annual_facts(gaap, tag)
            if facts:
                components.append((tag, facts))
        years = sorted({year for _, facts in components for year in facts})
        total = {
            year: sum(
                float(facts[year]["val"]) for _, facts in components if year in facts
            )
            for year in years
        }
        # ShortTermBorrowings is already inside the partial sum above.
        extra_tags = ["CommercialPaper"]

    # Commercial paper / short-term borrowings are usually outside the long-term
    # debt total, so add them when present.
    for tag in extra_tags:
        facts = edgar.annual_facts(gaap, tag)
        if not facts:
            continue
        components.append((tag, facts))
        for year, row in facts.items():
            if year in total:
                total[year] += float(row["val"])

    return total, components


def _share_series(
    gaap: dict[str, Any], dei: dict[str, Any]
) -> tuple[str, dict[int, float], dict[int, dict[str, Any]]]:
    tag, facts = edgar.best_facts(gaap, SHARE_TAGS, unit="shares")
    if facts:
        return tag or "unknown", {year: float(row["val"]) for year, row in facts.items()}, facts
    dei_facts = edgar.annual_facts(dei, "EntityCommonStockSharesOutstanding", unit="shares")
    if dei_facts:
        return (
            "dei:EntityCommonStockSharesOutstanding",
            {year: float(row["val"]) for year, row in dei_facts.items()},
            dei_facts,
        )
    return "missing", {}, {}


def _fact_rows(
    *,
    cik: str,
    filing: FilingInfo,
    metric: str,
    tag: str,
    facts: dict[int, dict[str, Any]],
    years: list[int] | tuple[int, ...],
    unit: str = "USD",
) -> list[dict[str, Any]]:
    """Flatten selected XBRL facts into provenance rows for the drill-down."""
    rows: list[dict[str, Any]] = []
    for year in years:
        fact = facts.get(year)
        if fact is None:
            continue
        accession = fact.get("accn") or filing.accession_number
        rows.append(
            {
                "metric": metric,
                "tag": tag,
                "fiscal_year": int(year),
                "value": float(fact["val"]),
                "unit": unit,
                "end": fact.get("end"),
                "filed": fact.get("filed"),
                "form": fact.get("form") or filing.form,
                "accession_number": accession,
                "url": edgar.filing_index_url(cik, accession),
            }
        )
    return rows


def _collect_source_facts(
    *,
    cik: str,
    filing: FilingInfo,
    series_facts: dict[str, tuple[str, dict[int, dict[str, Any]]]],
    debt_components: DebtComponents,
    share_source: str,
    share_facts: dict[int, dict[str, Any]],
    years: list[int],
    latest_year: int,
) -> list[dict[str, Any]]:
    """Provenance for every number the DCF consumes.

    Flow metrics get one row per history year; balance-sheet and share-count
    inputs only need the latest fiscal year, which is the one the DCF uses.
    """
    rows: list[dict[str, Any]] = []
    for metric, (tag, facts) in series_facts.items():
        if metric == "cash":
            continue
        rows.extend(
            _fact_rows(
                cik=cik,
                filing=filing,
                metric=metric,
                tag=tag,
                facts=facts,
                years=years,
            )
        )

    cash_tag, cash_facts = series_facts["cash"]
    rows.extend(
        _fact_rows(
            cik=cik,
            filing=filing,
            metric="cash",
            tag=cash_tag,
            facts=cash_facts,
            years=[latest_year],
        )
    )
    for tag, facts in debt_components:
        rows.extend(
            _fact_rows(
                cik=cik,
                filing=filing,
                metric="total_debt",
                tag=tag,
                facts=facts,
                years=[latest_year],
            )
        )
    rows.extend(
        _fact_rows(
            cik=cik,
            filing=filing,
            metric="shares_outstanding",
            tag=share_source,
            facts=share_facts,
            years=[latest_year],
            unit="shares",
        )
    )
    return rows


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
    series_facts: dict[str, tuple[str, dict[int, dict[str, Any]]]] = {}
    for metric, tags in METRIC_TAGS.items():
        tag, facts = edgar.best_facts(gaap, tags)
        series[metric] = {year: float(row["val"]) for year, row in facts.items()}
        series_facts[metric] = (tag or "unknown", facts)
        if not facts and metric == "revenue":
            flags.append("revenue_missing")

    debt, debt_components = _debt_series(gaap, flags)
    share_source, shares, share_facts = _share_series(gaap, dei)

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

    source_facts = _collect_source_facts(
        cik=cik,
        filing=filing,
        series_facts=series_facts,
        debt_components=debt_components,
        share_source=share_source,
        share_facts=share_facts,
        years=years,
        latest_year=latest_year,
    )

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
        source_facts=source_facts,
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
