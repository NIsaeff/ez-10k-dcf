"""Wizard proposal validation and impact. No network: analyze is faked."""

import pytest

from app.schemas import WizardContext
from app.services import valuation, wizard_proposals
from tests.conftest import company_from_fixture


@pytest.fixture
def fake_analyze(monkeypatch):
    def _analyze(ticker, overrides=None, allow_any=False):
        company = company_from_fixture("KO")
        company.ticker = ticker
        return valuation.analyze_from_company(company, overrides)

    monkeypatch.setattr(wizard_proposals.valuation, "analyze", _analyze)


def _context() -> WizardContext:
    return WizardContext(ticker="KO", years=5, terminal=2.5, model="fade")


def test_delta_is_relative_to_the_effective_value(fake_analyze) -> None:
    proposal = wizard_proposals.build_proposal(
        _context(),
        {
            "title": "Raise growth",
            "rationale": "Test a small upside case.",
            "confidence": 0.9,
            "changes": [{"key": "growth", "delta": 0.25}],
        },
    )

    change = proposal.changes[0]
    assert change.before == pytest.approx(1.2443, abs=0.01)
    assert change.after == pytest.approx(1.4943, abs=0.01)
    assert proposal.impact is not None
    assert proposal.impact["value_after"] > proposal.impact["value_before"]


def test_signed_string_is_treated_as_a_delta(fake_analyze) -> None:
    proposal = wizard_proposals.build_proposal(
        _context(),
        {
            "title": "Trim growth",
            "rationale": "Cautious case.",
            "confidence": 0.7,
            "changes": [{"key": "growth", "value": "-0.25"}],
        },
    )

    assert proposal.changes[0].after == pytest.approx(0.9943, abs=0.01)


def test_absolute_value_still_works(fake_analyze) -> None:
    proposal = wizard_proposals.build_proposal(
        _context(),
        {
            "title": "Set terminal growth",
            "rationale": "Mature company.",
            "confidence": 0.8,
            "changes": [{"key": "terminal", "value": 2.0}],
        },
    )

    assert proposal.changes[0].after == 2.0
    assert proposal.changes[0].before == pytest.approx(2.5)


def test_invalid_value_explains_the_expected_shape(fake_analyze) -> None:
    with pytest.raises(wizard_proposals.ProposalError) as excinfo:
        wizard_proposals.build_proposal(
            _context(),
            {
                "title": "Bad",
                "rationale": "Bad",
                "confidence": 0.5,
                "changes": [{"key": "growth", "value": "a quarter point"}],
            },
        )

    message = str(excinfo.value)
    assert "absolute number or a delta" in message
    assert "current effective" in message


def test_unknown_key_is_rejected(fake_analyze) -> None:
    with pytest.raises(wizard_proposals.ProposalError):
        wizard_proposals.build_proposal(
            _context(),
            {
                "title": "Bad",
                "rationale": "Bad",
                "confidence": 0.5,
                "changes": [{"key": "ebitda", "value": 1}],
            },
        )


def test_effective_values_are_exposed_for_the_prompt(fake_analyze) -> None:
    values, value_per_share = wizard_proposals.effective_values(_context())

    assert values["growth"] == pytest.approx(1.2443, abs=0.01)
    assert values["wacc"] == pytest.approx(7.5)
    assert values["model"] == "fade"
    assert value_per_share == pytest.approx(31.70, abs=0.01)
