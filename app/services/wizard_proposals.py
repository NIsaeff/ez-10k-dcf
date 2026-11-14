"""Wizard proposals: the model proposes, the human applies.

The chat can suggest changes to the DCF wizard (sliders or navigation). Nothing
is applied server-side: a proposal is validated, quantified with the real engine,
and returned for the UI to render. A human click is the only thing that moves
the wizard.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.schemas import (
    DcfOverrides,
    Proposal,
    ProposalChange,
    ProposalEvidence,
    ProposalNavigation,
    WizardContext,
)
from app.services import valuation

# key: (min, max, label) in the wizard's display units.
BOUNDS: dict[str, tuple[float | None, float | None, str]] = {
    "growth": (0.0, 25.0, "Growth (year 1)"),
    "tax": (0.0, 40.0, "Tax rate"),
    "capex": (0.0, 40.0, "CapEx (% of revenue)"),
    "wacc": (1.0, 30.0, "WACC"),
    "terminal": (1.0, 5.0, "Terminal growth"),
    "years": (3.0, 10.0, "Projection years"),
    "shares": (1.0, 100_000.0, "Shares outstanding (M)"),
    "model": (None, None, "Growth model"),
}

MAX_CHANGES = 5


class ProposalError(Exception):
    """The model asked for something we refuse to propose."""


def overrides_from_context(context: WizardContext) -> DcfOverrides:
    return DcfOverrides(
        projection_years=context.years,
        terminal_growth_rate=context.terminal / 100.0,
        growth_model=context.model,
        wacc=None if context.wacc is None else context.wacc / 100.0,
        growth_rate=None if context.growth is None else context.growth / 100.0,
        tax_rate=None if context.tax is None else context.tax / 100.0,
        capex_rate=None if context.capex is None else context.capex / 100.0,
        shares_outstanding=(
            None if context.shares is None else context.shares * 1_000_000.0
        ),
    )


def _validate_change(raw: dict[str, Any]) -> tuple[str, float | str]:
    key = str(raw.get("key") or "")
    if key not in BOUNDS:
        raise ProposalError(f"Unknown wizard key: {key}")

    value = raw.get("value")
    if key == "model":
        model = str(value or "").lower()
        if model not in ("fade", "constant"):
            raise ProposalError("Growth model must be 'fade' or 'constant'")
        return key, model

    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ProposalError(f"{key} needs a numeric value") from exc

    low, high, _label = BOUNDS[key]
    if low is not None and high is not None:
        number = max(low, min(high, number))
    return key, round(number, 4)


def _before_values(
    context: WizardContext, overrides: DcfOverrides
) -> tuple[dict[str, Any], float | None]:
    """Current effective values, from the real engine, in wizard units."""
    try:
        result = valuation.analyze(context.ticker, overrides, allow_any=True)
    except Exception:  # noqa: BLE001 - proposals without impact are still useful
        return {}, None

    assumptions = result.assumptions
    latest = result.history[-1]
    capex_rate = assumptions.capex_rate
    if capex_rate is None and latest.revenue:
        capex_rate = latest.capital_expenditures / latest.revenue

    return (
        {
            "growth": round(assumptions.growth_rate * 100, 4),
            "tax": round(assumptions.tax_rate * 100, 4),
            "capex": None if capex_rate is None else round(capex_rate * 100, 4),
            "wacc": round(assumptions.wacc * 100, 4),
            "terminal": round(assumptions.terminal_growth_rate * 100, 4),
            "years": assumptions.projection_years,
            "shares": round(result.valuation.shares_outstanding / 1_000_000, 2),
            "model": assumptions.growth_model,
        },
        result.valuation.value_per_share,
    )


def _context_with_changes(
    context: WizardContext, changes: list[tuple[str, float | str]]
) -> WizardContext:
    updated = context.model_copy()
    for key, value in changes:
        if key == "model":
            updated.model = value  # type: ignore[assignment]
        elif key == "years":
            updated.years = int(value)
        elif key == "shares":
            updated.shares = float(value)
        else:
            setattr(updated, key, float(value))
    return updated


def build_proposal(
    context: WizardContext,
    payload: dict[str, Any],
) -> Proposal:
    raw_changes = payload.get("changes")
    if not isinstance(raw_changes, list) or not raw_changes:
        raise ProposalError("A proposal needs at least one change")
    if len(raw_changes) > MAX_CHANGES:
        raise ProposalError(f"At most {MAX_CHANGES} changes per proposal")

    changes: list[tuple[str, float | str]] = []
    for raw in raw_changes:
        if isinstance(raw, dict):
            changes.append(_validate_change(raw))

    if not changes:
        raise ProposalError("No valid change survived validation")

    before_overrides = overrides_from_context(context)
    before_values, value_before = _before_values(context, before_overrides)

    updated = _context_with_changes(context, changes)
    value_after: float | None = None
    try:
        result = valuation.analyze(
            updated.ticker, overrides_from_context(updated), allow_any=True
        )
        value_after = result.valuation.value_per_share
    except Exception:  # noqa: BLE001 - still propose, just without impact
        value_after = None

    confidence = payload.get("confidence")
    try:
        overall = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        overall = 0.6

    rendered: list[ProposalChange] = []
    for key, value in changes:
        label = BOUNDS[key][2]
        rendered.append(
            ProposalChange(
                key=key,
                label=label,
                before=before_values.get(key),
                after=value,
                confidence=overall,
            )
        )

    evidence: list[ProposalEvidence] = []
    for item in payload.get("evidence") or []:
        if not isinstance(item, dict):
            continue
        evidence.append(
            ProposalEvidence(
                type=str(item.get("type") or "note")[:32],
                label=str(item.get("label") or "")[:200],
                ref=str(item.get("ref") or "") or None,
                quote=str(item.get("quote") or "")[:400] or None,
            )
        )

    return Proposal(
        id=f"act_{uuid.uuid4().hex[:8]}",
        kind="assumptions",
        title=str(payload.get("title") or "Proposed change")[:120],
        changes=rendered,
        rationale=str(payload.get("rationale") or "")[:400],
        evidence=evidence,
        impact=(
            {"value_before": value_before, "value_after": value_after}
            if value_before is not None and value_after is not None
            else None
        ),
        confidence=overall,
        navigation=None,
    )


def build_navigation(
    context: WizardContext,
    payload: dict[str, Any],
) -> Proposal:
    from app.services import edgar

    ticker = str(payload.get("ticker") or "").upper().strip() or None
    tab = str(payload.get("tab") or "").lower().strip() or None
    claim = str(payload.get("claim_id") or "").strip() or None

    if tab is not None and tab not in ("fcff", "wacc", "dcf", "filing"):
        tab = None
    if ticker is not None:
        try:
            edgar.company_info(ticker)
        except KeyError as exc:
            raise ProposalError(f"Unknown ticker: {ticker}") from exc

    if ticker is None and tab is None and claim is None:
        raise ProposalError("Navigation needs a ticker, tab or claim")

    changes: list[ProposalChange] = []
    if ticker is not None and ticker != context.ticker:
        changes.append(
            ProposalChange(
                key="ticker", label="Ticker", before=context.ticker, after=ticker
            )
        )
    if tab is not None:
        changes.append(
            ProposalChange(key="tab", label="Open tab", before=context.tab, after=tab)
        )
    if claim is not None:
        changes.append(
            ProposalChange(
                key="claim_id", label="Filing claim", before=None, after=claim
            )
        )

    if not changes:
        raise ProposalError("Nothing to navigate to")

    confidence = payload.get("confidence")
    try:
        overall = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        overall = 0.95

    return Proposal(
        id=f"act_{uuid.uuid4().hex[:8]}",
        kind="navigate",
        title=str(payload.get("title") or "Open in the workspace")[:120],
        changes=changes,
        rationale=str(payload.get("rationale") or "")[:400],
        evidence=[],
        impact=None,
        confidence=overall,
        navigation=ProposalNavigation(ticker=ticker, tab=tab, claim_id=claim),
    )


def explain(context: WizardContext, key: str) -> str:
    """Return the P1 review for one assumption, as text for the model."""
    from app.services import assumptions, edgar

    try:
        info = edgar.company_info(context.ticker)
        meta = edgar.latest_10k(int(info["cik"]))
        cached = assumptions.load_cached(meta["accession_number"])
    except Exception:  # noqa: BLE001 - explanation is optional
        return "No filing review is cached for this ticker yet."

    if cached is None:
        return "No filing review is cached for this ticker yet."

    for review in cached.get("reviews", []):
        if review.get("key") == "growth_rate":
            quotes = [
                f"- {item['quote']} ({item.get('section')})"
                for item in review.get("evidence", [])[:4]
                if item.get("quote")
            ]
            return (
                f"stance={review.get('stance')} lean={review.get('lean')} "
                f"engine={review.get('engine_value')} "
                f"range={review.get('suggested_range')}\n"
                + "\n".join(quotes)
            )
    return "No review for that key."
