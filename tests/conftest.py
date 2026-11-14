import json
from pathlib import Path

import pytest

from app.config import settings
from app.schemas import FilingInfo
from app.services import macro
from app.services.financials import CompanyFinancials, build_from_facts

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def offline_macro(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Tests never reach FRED or reuse a developer cache; macro tests opt in."""
    monkeypatch.setattr(settings, "fred_api_key", "")
    monkeypatch.setattr(macro, "CACHE_DIR", tmp_path / "fred")


def load_fixture(ticker: str) -> dict:
    return json.loads((FIXTURE_DIR / f"{ticker}.json").read_text())


def company_from_fixture(ticker: str) -> CompanyFinancials:
    data = load_fixture(ticker)
    return build_from_facts(
        ticker=ticker,
        company_name=data["company_name"],
        cik=data["cik"],
        filing=FilingInfo(**data["filing"]),
        facts=data,
    )


@pytest.fixture(params=["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "KO", "PWR"])
def ticker(request: pytest.FixtureRequest) -> str:
    return request.param
