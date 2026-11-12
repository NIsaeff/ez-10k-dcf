"""CAPM / WACC decomposition."""

import pytest

from app.services import dcf
from app.services import wacc as wacc_service
from app.services.market import MarketInputs
from tests.conftest import company_from_fixture


def _market(**overrides) -> MarketInputs:
    values = {
        "ticker": "KO",
        "price": 60.0,
        "beta_computed": 0.55,
        "beta_reported": 0.60,
        "beta_observations": 104,
        "beta_r_squared": 0.35,
        "risk_free_rate": 0.042,
        "as_of": "2026-11-11",
        "available": True,
    }
    values.update(overrides)
    return MarketInputs(**values)


def test_capm_breakdown_math() -> None:
    company = company_from_fixture("KO")
    breakdown = wacc_service.build_wacc(company, _market(), fallback_wacc=0.075)

    expected_equity = 0.042 + 0.55 * wacc_service.ERP_DEFAULT
    assert breakdown.cost_of_equity == pytest.approx(expected_equity)
    assert breakdown.market_cap == pytest.approx(60.0 * company.shares_outstanding)
    assert breakdown.weight_equity + breakdown.weight_debt == pytest.approx(1.0)
    assert breakdown.wacc == pytest.approx(
        breakdown.weight_equity * breakdown.cost_of_equity
        + breakdown.weight_debt * breakdown.cost_of_debt
    )
    assert breakdown.wacc > 0
    assert "capm_incomplete" not in breakdown.flags


def test_every_input_carries_a_source() -> None:
    breakdown = wacc_service.build_wacc(
        company_from_fixture("KO"), _market(), fallback_wacc=0.075
    )

    keys = {item.key for item in breakdown.inputs}
    assert {
        "risk_free_rate",
        "beta",
        "erp",
        "cost_of_equity",
        "cost_of_debt",
        "tax_rate",
        "weight_equity",
        "weight_debt",
    } <= keys
    assert all(item.source for item in breakdown.inputs)

    sources = {item.key: item.source for item in breakdown.inputs}
    assert "TNX" in sources["risk_free_rate"]
    assert "assumption" in sources["erp"]
    # Trimmed test fixtures have no interest-expense tag, so this exercises the
    # documented default path; test_cost_of_debt_uses_sec_tag covers the SEC one.
    assert sources["cost_of_debt"]


def test_cost_of_debt_uses_sec_tag_when_present() -> None:
    company = company_from_fixture("KO")
    company.raw_years[-1]["interest_expense"] = 1_000_000_000

    breakdown = wacc_service.build_wacc(company, _market(), fallback_wacc=0.075)

    cost_of_debt = next(item for item in breakdown.inputs if item.key == "cost_of_debt")
    assert "InterestExpense" in cost_of_debt.source
    assert "cost_of_debt_default" not in breakdown.flags
    pre_tax = min(max(1_000_000_000 / company.total_debt, 0.005), 0.15)
    latest = company.raw_years[-1]
    tax_rate, _ = dcf.effective_tax_rate(
        latest.get("tax_expense"), latest.get("pretax_income")
    )
    assert cost_of_debt.value == pytest.approx(pre_tax * (1.0 - tax_rate), abs=1e-9)


def test_unreliable_beta_falls_back_to_reported() -> None:
    breakdown = wacc_service.build_wacc(
        company_from_fixture("KO"),
        _market(flags=["beta_unreliable"]),
        fallback_wacc=0.075,
    )

    beta_input = next(item for item in breakdown.inputs if item.key == "beta")
    assert beta_input.value == 0.60
    assert "yahoo" in beta_input.source
    assert "beta_from_reported" in breakdown.flags


def test_unreliable_beta_without_reported_uses_market_beta() -> None:
    breakdown = wacc_service.build_wacc(
        company_from_fixture("KO"),
        _market(flags=["beta_unreliable"], beta_reported=None),
        fallback_wacc=0.075,
    )

    beta_input = next(item for item in breakdown.inputs if item.key == "beta")
    assert beta_input.value == wacc_service.DEFAULT_BETA
    assert "default" in beta_input.source
    assert "beta_default" in breakdown.flags


def test_missing_risk_free_falls_back_to_manual_wacc() -> None:
    breakdown = wacc_service.build_wacc(
        company_from_fixture("KO"),
        _market(risk_free_rate=None),
        fallback_wacc=0.075,
    )

    assert breakdown.wacc == 0.075
    assert breakdown.cost_of_equity is None
    assert breakdown.cost_of_debt is None
    assert "capm_incomplete" in breakdown.flags


def test_market_cap_computed_from_price_and_sec_shares() -> None:
    company = company_from_fixture("KO")
    yahoo_market_cap = 300_000_000_000

    computed = wacc_service.build_wacc(company, _market(), fallback_wacc=0.075)
    given = wacc_service.build_wacc(
        company, _market(market_cap=yahoo_market_cap), fallback_wacc=0.075
    )

    assert computed.market_cap == pytest.approx(60.0 * company.shares_outstanding)
    assert given.market_cap == yahoo_market_cap

    computed_source = next(
        item.source for item in computed.inputs if item.key == "market_cap"
    )
    given_source = next(
        item.source for item in given.inputs if item.key == "market_cap"
    )
    assert "computed" in computed_source
    assert "yahoo" in given_source
