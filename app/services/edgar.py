"""SEC EDGAR client and XBRL helpers.

All responses are cached under data/raw/ (gitignored). Tests use trimmed fixtures
instead of network access.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from app.config import settings

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"

HEADERS = {
    "User-Agent": settings.sec_user_agent,
    "Accept": "application/json",
}


def _cache_path(name: str) -> Path:
    path = settings.data_dir / "raw" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _get_json(url: str, cache_name: str, *, timeout: float = 60.0) -> dict[str, Any]:
    path = _cache_path(cache_name)
    if path.exists():
        return json.loads(path.read_text())
    response = httpx.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    payload = response.json()
    path.write_text(json.dumps(payload))
    return payload


def ticker_map() -> dict[str, dict[str, Any]]:
    payload = _get_json(TICKERS_URL, "company_tickers.json")
    result: dict[str, dict[str, Any]] = {}
    for row in payload.values():
        ticker = str(row["ticker"]).upper()
        result[ticker] = {
            "cik": int(row["cik_str"]),
            "title": str(row["title"]),
        }
    return result


def company_info(ticker: str) -> dict[str, Any]:
    ticker = ticker.upper()
    info = ticker_map().get(ticker)
    if info is None:
        raise KeyError(f"Unknown ticker: {ticker}")
    return info


def submissions(cik: int) -> dict[str, Any]:
    return _get_json(SUBMISSIONS_URL.format(cik=cik), f"submissions_{cik:010d}.json")


def latest_10k(cik: int) -> dict[str, Any]:
    payload = submissions(cik)
    recent = payload.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    for index, form in enumerate(forms):
        if form != "10-K":
            continue
        accession = recent["accessionNumber"][index]
        document = recent["primaryDocument"][index]
        return {
            "accession_number": accession,
            "form": "10-K",
            "fiscal_year_end": recent["reportDate"][index],
            "filed": recent["filingDate"][index],
            "url": ARCHIVE_URL.format(
                cik=cik,
                accession=accession.replace("-", ""),
                document=document,
            ),
        }
    raise ValueError(f"No 10-K filing found for CIK {cik}")


def companyfacts(cik: int) -> dict[str, Any]:
    return _get_json(COMPANYFACTS_URL.format(cik=cik), f"companyfacts_{cik:010d}.json")


def annual_facts(
    gaap: dict[str, Any], tag: str, unit: str = "USD"
) -> dict[int, dict[str, Any]]:
    """Map fiscal year -> the winning annual 10-K fact for that year.

    Deduplicates by (fy, end) preferring the latest filing, then by fy preferring
    the latest period end. Keeps the whole fact row (val, end, filed, accn) so
    callers can show provenance, not just the number.
    """
    units = gaap.get(tag, {}).get("units", {}).get(unit, [])
    rows = [
        row
        for row in units
        if row.get("form") == "10-K"
        and row.get("fp") == "FY"
        and row.get("end")
        and row.get("fy") is not None
    ]
    best: dict[tuple[int, str], dict[str, Any]] = {}
    for row in rows:
        key = (int(row["fy"]), str(row["end"]))
        if key not in best or str(row.get("filed", "")) > str(best[key].get("filed", "")):
            best[key] = row

    result: dict[int, dict[str, Any]] = {}
    for (fiscal_year, end), row in sorted(best.items(), key=lambda item: (item[0][1], item[0][0])):
        result[fiscal_year] = row
    return result


def annual_series(gaap: dict[str, Any], tag: str, unit: str = "USD") -> dict[int, float]:
    """Map fiscal year -> value for annual 10-K facts."""
    return {year: float(row["val"]) for year, row in annual_facts(gaap, tag, unit).items()}


def best_facts(
    gaap: dict[str, Any],
    tags: list[str],
    unit: str = "USD",
) -> tuple[str | None, dict[int, dict[str, Any]]]:
    """Pick the candidate tag with the most recent coverage, then the most years."""
    best_tag: str | None = None
    best_rows: dict[int, dict[str, Any]] = {}
    best_score = (-1, -1)
    for tag in tags:
        rows = annual_facts(gaap, tag, unit)
        if not rows:
            continue
        score = (max(rows), len(rows))
        if score > best_score:
            best_tag, best_rows, best_score = tag, rows, score
    return best_tag, best_rows


def best_series(
    gaap: dict[str, Any],
    tags: list[str],
    unit: str = "USD",
) -> tuple[str | None, dict[int, float]]:
    tag, rows = best_facts(gaap, tags, unit)
    return tag, {year: float(row["val"]) for year, row in rows.items()}


def filing_index_url(cik: str, accession_number: str) -> str:
    """SEC filing index page for an accession (the folder holding the XBRL files)."""
    return (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accession_number.replace('-', '')}/"
    )
