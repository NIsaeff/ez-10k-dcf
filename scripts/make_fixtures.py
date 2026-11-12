"""Build trimmed SEC fixtures for offline tests.

Usage:
    uv run python -m scripts.make_fixtures
"""

import json
from pathlib import Path

from app.services import edgar
from app.services.financials import METRIC_TAGS, SHARE_TAGS
from app.services.valuation import SUPPORTED_TICKERS

DEBT_TAGS = [
    "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities",
    "DebtLongtermAndShorttermCombinedAmount",
    "LongTermDebt",
    "LongTermDebtNoncurrent",
    "LongTermDebtCurrent",
    "ShortTermBorrowings",
    "DebtCurrent",
    "CommercialPaper",
]

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def _annual_rows(units: dict[str, list[dict]], unit: str) -> list[dict]:
    return [
        row
        for row in units.get(unit, [])
        if row.get("form") == "10-K" and row.get("fp") == "FY" and row.get("fy")
    ]


def trim_facts(facts: dict) -> dict:
    gaap = facts.get("facts", {}).get("us-gaap", {})
    dei = facts.get("facts", {}).get("dei", {})
    tags = set(DEBT_TAGS) | set(SHARE_TAGS)
    for names in METRIC_TAGS.values():
        tags.update(names)

    trimmed_gaap: dict[str, dict] = {}
    for tag in sorted(tags):
        if tag not in gaap:
            continue
        units: dict[str, list[dict]] = {}
        for unit in gaap[tag].get("units", {}):
            annual = _annual_rows(gaap[tag].get("units", {}), unit)
            if annual:
                units[unit] = annual
        if units:
            trimmed_gaap[tag] = {"units": units}

    trimmed_dei: dict[str, dict] = {}
    if "EntityCommonStockSharesOutstanding" in dei:
        units = {}
        for unit in dei["EntityCommonStockSharesOutstanding"].get("units", {}):
            annual = _annual_rows(dei["EntityCommonStockSharesOutstanding"]["units"], unit)
            if annual:
                units[unit] = annual
        if units:
            trimmed_dei["EntityCommonStockSharesOutstanding"] = {"units": units}

    return {"facts": {"us-gaap": trimmed_gaap, "dei": trimmed_dei}}


def main() -> int:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    tickers = edgar.ticker_map()
    for ticker in SUPPORTED_TICKERS:
        info = tickers[ticker]
        cik = int(info["cik"])
        filing = edgar.latest_10k(cik)
        facts = edgar.companyfacts(cik)
        payload = {
            "ticker": ticker,
            "company_name": info["title"],
            "cik": f"{cik:010d}",
            "filing": filing,
            **trim_facts(facts),
        }
        path = FIXTURE_DIR / f"{ticker}.json"
        path.write_text(json.dumps(payload, separators=(",", ":")))
        print(f"{ticker}: {path.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
