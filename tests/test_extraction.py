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


def test_source_facts_trace_every_input(ticker: str) -> None:
    company = company_from_fixture(ticker)
    result = valuation.analyze_from_company(company)
    latest = result.history[-1].fiscal_year

    grouped: dict[str, list] = {}
    for fact in result.source_facts:
        grouped.setdefault(fact.metric, []).append(fact)
        assert fact.tag
        assert fact.url.startswith("https://www.sec.gov/Archives/edgar/data/")
        assert fact.unit in {"USD", "shares"}

    for metric in (
        "ebit",
        "depreciation_amortization",
        "capital_expenditures",
        "cash",
        "total_debt",
        "shares_outstanding",
    ):
        assert metric in grouped, f"{ticker}: no provenance for {metric}"
        assert any(fact.fiscal_year == latest for fact in grouped[metric])

    latest_ebit = next(
        fact.value for fact in grouped["ebit"] if fact.fiscal_year == latest
    )
    assert latest_ebit == result.history[-1].ebit


def test_source_facts_reconcile_with_summary() -> None:
    result = valuation.analyze_from_company(company_from_fixture("KO"))
    latest = result.history[-1].fiscal_year

    debt = sum(
        fact.value
        for fact in result.source_facts
        if fact.metric == "total_debt" and fact.fiscal_year == latest
    )
    cash = next(
        fact.value
        for fact in result.source_facts
        if fact.metric == "cash" and fact.fiscal_year == latest
    )
    shares = next(
        fact.value
        for fact in result.source_facts
        if fact.metric == "shares_outstanding" and fact.fiscal_year == latest
    )

    assert debt == result.valuation.total_debt
    assert cash == result.valuation.cash_and_equivalents
    assert shares == result.valuation.shares_outstanding


def test_history_fcff_matches_dcf() -> None:
    company = company_from_fixture("KO")
    history, _ = dcf.build_history(company.raw_years)
    assert history
    for year in history:
        assert year.fcff == year.fcff  # not NaN
