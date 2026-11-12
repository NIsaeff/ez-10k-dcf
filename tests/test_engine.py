"""Engine overrides, growth models, and the sensitivity grid."""

import pytest

from app.schemas import DcfOverrides
from app.services import dcf, valuation
from app.services.valuation import InvalidAssumptions
from tests.conftest import company_from_fixture


def test_engine_matches_assumptions() -> None:
    result = valuation.analyze_from_company(company_from_fixture("AAPL"))
    engine = result.engine

    assert engine is not None
    assert engine.wacc == result.assumptions.wacc
    assert engine.base_wacc == valuation.WACC_DEFAULTS[result.ticker]
    assert engine.base_fcff == result.assumptions.fcff_base
    assert engine.growth_model == result.assumptions.growth_model
    assert engine.terminal_growth_rate == result.assumptions.terminal_growth_rate
    assert engine.projection_years == result.assumptions.projection_years
    assert engine.total_debt == result.valuation.total_debt
    assert engine.cash == result.valuation.cash_and_equivalents
    assert engine.shares_outstanding == result.valuation.shares_outstanding
    assert engine.base_year == result.history[-1].fiscal_year


def test_overrides_are_applied_and_reported() -> None:
    company = company_from_fixture("KO")
    base = valuation.analyze_from_company(company)
    bumped = valuation.analyze_from_company(
        company,
        DcfOverrides(
            projection_years=7,
            terminal_growth_rate=0.03,
            wacc=0.09,
        ),
    )

    assert bumped.assumptions.projection_years == 7
    assert bumped.assumptions.terminal_growth_rate == 0.03
    assert bumped.assumptions.wacc == 0.09
    assert bumped.assumptions.wacc_source == "override"
    assert len(bumped.projection) == 7
    assert set(bumped.overrides_applied) == {
        "projection_years",
        "terminal_growth_rate",
        "wacc",
    }
    # A 9% discount rate must value the company below the 7.5% default.
    assert bumped.valuation.value_per_share < base.valuation.value_per_share
    assert "wacc_manual_default" not in bumped.flags


def test_growth_model_selector_changes_the_path() -> None:
    company = company_from_fixture("KO")
    overrides = {"growth_rate": 0.08, "terminal_growth_rate": 0.025}

    fade = valuation.analyze_from_company(
        company, DcfOverrides(growth_model="fade", **overrides)
    )
    constant = valuation.analyze_from_company(
        company, DcfOverrides(growth_model="constant", **overrides)
    )

    assert fade.assumptions.growth_model == "fade"
    assert constant.assumptions.growth_model == "constant"
    # Holding 8% beats fading 8% -> 2.5%.
    assert constant.valuation.value_per_share > fade.valuation.value_per_share
    assert constant.projection[0].fcff == pytest.approx(fade.projection[0].fcff)


def test_invalid_assumptions_raise() -> None:
    company = company_from_fixture("KO")
    with pytest.raises(InvalidAssumptions):
        valuation.analyze_from_company(
            company, DcfOverrides(wacc=0.02, terminal_growth_rate=0.03)
        )


def test_project_fcff_rejects_unknown_model() -> None:
    with pytest.raises(ValueError):
        dcf.project_fcff(
            base_fcff=1.0,
            growth_rate=0.1,
            terminal_growth_rate=0.02,
            base_year=2025,
            wacc=0.09,
            growth_model="sideways",
        )


def test_sensitivity_grid_shape_and_monotonicity() -> None:
    engine = valuation.analyze_from_company(company_from_fixture("KO")).engine
    assert engine is not None

    wacc_values, growth_values, values = dcf.sensitivity_grid(
        base_fcff=engine.base_fcff,
        growth_rate=engine.growth_rate,
        growth_model=engine.growth_model,
        terminal_growth_rate=engine.terminal_growth_rate,
        base_year=engine.base_year,
        years=engine.projection_years,
        wacc=engine.wacc,
        total_debt=engine.total_debt,
        cash_and_equivalents=engine.cash,
        shares_outstanding=engine.shares_outstanding,
    )

    assert len(wacc_values) == 5
    assert len(growth_values) == 5
    assert len(values) == 5
    assert all(len(row) == 5 for row in values)

    middle_column = [row[2] for row in values]
    assert middle_column == sorted(middle_column, reverse=True)

    middle_row = values[2]
    assert middle_row == sorted(middle_row)


def test_sensitivity_returns_none_below_terminal_growth() -> None:
    engine = valuation.analyze_from_company(company_from_fixture("KO")).engine
    assert engine is not None

    _wacc_values, _growth_values, values = dcf.sensitivity_grid(
        base_fcff=engine.base_fcff,
        growth_rate=engine.growth_rate,
        growth_model=engine.growth_model,
        terminal_growth_rate=engine.terminal_growth_rate,
        base_year=engine.base_year,
        years=engine.projection_years,
        wacc=0.03,
        total_debt=engine.total_debt,
        cash_and_equivalents=engine.cash,
        shares_outstanding=engine.shares_outstanding,
        wacc_span=0.02,
        growth_span=0.01,
    )

    assert any(cell is None for row in values for cell in row)
    # Teams that would divide by a negative spread are blank, not inf.
    assert all(cell is None or cell > 0 for row in values for cell in row)
