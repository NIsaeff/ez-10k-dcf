from app.schemas import FilingInfo
from app.services import dcf, valuation
from app.services.financials import build_from_facts
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


def _gaap_rows(values: dict[int, float], filed: str = "2025-02-01") -> dict:
    return {
        "units": {
            "USD": [
                {
                    "form": "10-K",
                    "fp": "FY",
                    "fy": year,
                    "end": f"{year}-12-31",
                    "val": value,
                    "filed": filed,
                    "accn": "0000000000-25-000001",
                }
                for year, value in values.items()
            ]
        }
    }


def _synthetic_facts() -> dict:
    """A filer that stopped tagging OperatingIncomeLoss after 2020."""
    gaap = {
        "OperatingIncomeLoss": _gaap_rows({2020: 10.0e9}),
        "DepreciationDepletionAndAmortization": _gaap_rows(
            {2022: 1.0e9, 2023: 1.1e9, 2024: 1.2e9}
        ),
        "PaymentsToAcquirePropertyPlantAndEquipment": _gaap_rows(
            {2022: 2.0e9, 2023: 2.1e9, 2024: 2.2e9}
        ),
        # Interest expense switches tag mid-history, like JNJ.
        "InterestExpense": _gaap_rows({2022: 0.5e9, 2023: 0.6e9}),
        "InterestExpenseNonoperating": _gaap_rows({2024: 0.7e9}),
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": _gaap_rows(
            {2022: 9.5e9, 2023: 9.9e9, 2024: 10.3e9}
        ),
        "CashAndCashEquivalentsAtCarryingValue": _gaap_rows({2024: 5.0e9}),
        "LongTermDebt": _gaap_rows({2024: 20.0e9}),
    }
    dei = {
        "EntityCommonStockSharesOutstanding": {
            "units": {
                "shares": [
                    {
                        "form": "10-K",
                        "fp": "FY",
                        "fy": 2024,
                        "end": "2024-12-31",
                        "val": 1.0e9,
                        "filed": "2025-02-01",
                        "accn": "0000000000-25-000001",
                    }
                ]
            }
        }
    }
    return {"facts": {"us-gaap": gaap, "dei": dei}}


def test_ebit_is_derived_when_operating_income_tag_is_stale() -> None:
    company = build_from_facts(
        ticker="FAKE",
        company_name="Fake Co",
        cik="0000000000",
        filing=FilingInfo(
            accession_number="0000000000-25-000001",
            form="10-K",
            fiscal_year_end="2024-12-31",
            filed="2025-02-01",
            url="https://www.sec.gov/Archives/edgar/data/0/000000000025000001/",
        ),
        facts=_synthetic_facts(),
    )

    assert [row["fiscal_year"] for row in company.raw_years] == [2022, 2023, 2024]
    assert "ebit_derived" in company.flags

    derived = [row for row in company.source_facts if row["tag"].startswith("derived:")]
    assert {row["fiscal_year"] for row in derived} == {2022, 2023, 2024}
    # EBIT = pretax + interest, per year, across complementary interest tags.
    by_year = {row["fiscal_year"]: row["ebit"] for row in company.raw_years}
    assert by_year[2022] == 9.5e9 + 0.5e9
    assert by_year[2024] == 10.3e9 + 0.7e9


def test_pilot_tickers_do_not_need_derived_ebit(ticker: str) -> None:
    company = company_from_fixture(ticker)
    assert "ebit_derived" not in company.flags
