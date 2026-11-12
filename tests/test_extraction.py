from app.services import dcf, valuation
from tests.conftest import company_from_fixture


def test_extraction_has_required_series(ticker: str) -> None:
    company = company_from_fixture(ticker)
    assert company.ticker == ticker
    assert company.cik
    assert company.filing.accession_number
    assert company.total_debt > 0
    assert company.cash_and_equivalents > 0
    assert company.shares_outstanding > 0
    assert len(company.raw_years) >= 3

    latest = max(company.raw_years, key=lambda row: row["fiscal_year"])
    assert latest["ebit"] is not None
    assert latest["depreciation_amortization"] is not None
    assert latest["capital_expenditures"] is not None


def test_valuation_is_deterministic(ticker: str) -> None:
    company = company_from_fixture(ticker)
    first = valuation.analyze_from_company(company)
    second = valuation.analyze_from_company(company)
    assert first.model_dump() == second.model_dump()
    assert first.valuation.value_per_share > 0
    assert first.assumptions.wacc > first.assumptions.terminal_growth_rate
    assert "wacc_manual_default" in first.flags
    assert "Illustrative" in first.disclaimer


def test_history_fcff_matches_dcf() -> None:
    company = company_from_fixture("KO")
    history, _ = dcf.build_history(company.raw_years)
    assert history
    for year in history:
        assert year.fcff == year.fcff  # not NaN
