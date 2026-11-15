import pytest

from app.services import dcf


def test_effective_tax_rate_clamps_and_defaults() -> None:
    assert dcf.effective_tax_rate(21.0, 100.0) == (0.21, False)
    assert dcf.effective_tax_rate(-10.0, 100.0) == (0.0, False)
    assert dcf.effective_tax_rate(60.0, 100.0) == (0.35, False)
    assert dcf.effective_tax_rate(None, 100.0) == (0.21, True)
    assert dcf.effective_tax_rate(10.0, -5.0) == (0.21, True)


def test_build_history_computes_fcff_and_nwc() -> None:
    raw = [
        {
            "fiscal_year": 2023,
            "ebit": 100.0,
            "pretax_income": 100.0,
            "tax_expense": 21.0,
            "depreciation_amortization": 10.0,
            "capital_expenditures": 20.0,
            "current_assets": 50.0,
            "current_liabilities": 30.0,
        },
        {
            "fiscal_year": 2024,
            "ebit": 110.0,
            "pretax_income": 110.0,
            "tax_expense": 23.1,
            "depreciation_amortization": 12.0,
            "capital_expenditures": 22.0,
            "current_assets": 60.0,
            "current_liabilities": 32.0,
        },
    ]
    history, flags = dcf.build_history(raw)
    assert [year.fiscal_year for year in history] == [2023, 2024]
    assert history[0].change_in_nwc == 0.0
    assert history[1].change_in_nwc == pytest.approx(8.0)
    assert history[0].fcff == pytest.approx(100 * 0.79 + 10 - 20)
    assert history[1].fcff == pytest.approx(110 * 0.79 + 12 - 22 - 8)
    assert "nwc_unavailable" not in flags


def test_build_history_flags_missing_nwc() -> None:
    raw = [
        {
            "fiscal_year": 2024,
            "ebit": 100.0,
            "depreciation_amortization": 10.0,
            "capital_expenditures": 20.0,
        }
    ]
    _, flags = dcf.build_history(raw)
    assert "nwc_unavailable" in flags
    assert "history_lt_3y" in flags


def test_select_fcff_base_filters_outliers() -> None:
    from app.schemas import YearFinancials

    def year(fy: int, fcff: float) -> YearFinancials:
        return YearFinancials(
            fiscal_year=fy,
            ebit=1.0,
            depreciation_amortization=1.0,
            capital_expenditures=1.0,
            fcff=fcff,
        )

    history = [year(2021, 8.0), year(2022, 9.0), year(2023, 10.0), year(2024, 1.0)]
    base, source, flags = dcf.select_fcff_base(history)
    assert source == "normalized_average"
    assert "fcff_base_normalized" in flags
    assert base == pytest.approx(9.0)


def test_terminal_value_and_valuation() -> None:
    projection = dcf.project_fcff(
        base_fcff=100.0,
        growth_rate=0.05,
        terminal_growth_rate=0.025,
        base_year=2024,
        wacc=0.10,
        years=5,
    )
    assert projection[0].year == 2025
    assert projection[-1].year == 2029

    summary, flags = dcf.build_valuation(
        projection=projection,
        terminal_growth_rate=0.025,
        wacc=0.10,
        total_debt=200.0,
        cash_and_equivalents=50.0,
        shares_outstanding=10.0,
    )
    assert summary.enterprise_value > 0
    assert summary.net_debt == pytest.approx(150.0)
    assert summary.value_per_share == pytest.approx(
        (summary.enterprise_value - 150.0) / 10.0
    )
    assert flags == []


def test_wacc_must_exceed_growth() -> None:
    with pytest.raises(ValueError):
        dcf.terminal_value(100.0, terminal_growth_rate=0.05, wacc=0.05)
