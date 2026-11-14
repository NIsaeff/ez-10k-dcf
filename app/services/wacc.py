"""CAPM / WACC decomposition with per-input provenance.

Every number here is either fetched (SEC, Yahoo), computed from fetched inputs,
or an explicit assumption. Nothing is silently invented: when a CAPM input is
missing, the breakdown falls back to the manual default WACC and says so.
"""

from __future__ import annotations

from app.schemas import WaccBreakdown, WaccInput
from app.services import dcf, financials
from app.services.market import MarketInputs

ERP_DEFAULT = 0.045
ERP_SOURCE = "assumption: Damodaran implied ERP / Kroll recommended, midpoint"
ERP_AS_OF = "2026-11"
DEFAULT_BETA = 1.0
COST_OF_DEBT_BOUNDS = (0.005, 0.15)


def _input(
    key: str,
    label: str,
    value: float | None,
    source: str,
    detail: str | None = None,
) -> WaccInput:
    return WaccInput(key=key, label=label, value=value, source=source, detail=detail)


def select_beta(market: MarketInputs) -> tuple[float, str, list[str]]:
    """Pick the beta CAPM should use, and say where it came from."""
    flags: list[str] = []

    if market.beta_computed is not None and "beta_unreliable" not in market.flags:
        return market.beta_computed, "computed: 2y weekly vs ^GSPC", flags

    if market.beta_reported is not None:
        flags.append("beta_from_reported")
        return market.beta_reported, "yahoo: defaultKeyStatistics.beta", flags

    flags.append("beta_default")
    return DEFAULT_BETA, "default: market beta (computed beta unusable)", flags


def build_wacc(
    company: financials.CompanyFinancials,
    market: MarketInputs,
    *,
    fallback_wacc: float,
    erp: float = ERP_DEFAULT,
) -> WaccBreakdown:
    flags = list(market.flags)
    inputs: list[WaccInput] = []

    beta, beta_source, beta_flags = select_beta(market)
    flags.extend(beta_flags)

    r_squared = market.beta_r_squared
    beta_detail = (
        f"R²={r_squared:.2f}, n={market.beta_observations}"
        if r_squared is not None
        else ("published by Yahoo" if "reported" in beta_source else None)
    )

    erp_input = _input(
        "erp",
        "Equity risk premium",
        erp,
        ERP_SOURCE,
        f"as of {ERP_AS_OF}; editable assumption",
    )

    # Market cap: Yahoo's when available, otherwise price x SEC shares.
    market_cap = market.market_cap
    market_cap_source = "yahoo: quoteSummary.price.marketCap"
    if market_cap is None and market.price is not None:
        market_cap = market.price * company.shares_outstanding
        market_cap_source = "computed: Yahoo price x SEC diluted shares"
    if market_cap is None:
        market_cap_source = "unavailable"

    risk_free = market.risk_free_rate
    if risk_free is None or market_cap is None:
        flags.append("capm_incomplete")
        inputs.extend(
            [
                _input(
                    "risk_free_rate",
                    "Risk-free rate",
                    risk_free,
                    market.risk_free_source or "unavailable",
                ),
                _input("beta", "Beta", beta, beta_source, beta_detail),
                erp_input,
                _input(
                    "market_cap",
                    "Market capitalisation",
                    market_cap,
                    market_cap_source,
                ),
            ]
        )
        return WaccBreakdown(
            ticker=company.ticker,
            wacc=fallback_wacc,
            cost_of_equity=None,
            cost_of_debt=None,
            weight_equity=None,
            weight_debt=None,
            market_cap=market_cap,
            price=market.price,
            as_of=market.as_of,
            inputs=inputs,
            flags=list(dict.fromkeys(flags)),
        )

    debt = company.total_debt
    total = market_cap + debt
    weight_equity = market_cap / total if total > 0 else 1.0
    weight_debt = debt / total if total > 0 else 0.0

    latest = company.raw_years[-1] if company.raw_years else {}
    tax_rate, tax_default = dcf.effective_tax_rate(
        latest.get("tax_expense"), latest.get("pretax_income")
    )

    interest = latest.get("interest_expense")
    if debt > 0 and interest is not None:
        cost_of_debt_pre_tax = dcf.clamp(interest / debt, *COST_OF_DEBT_BOUNDS)
        cost_of_debt_source = "sec: InterestExpense / total debt"
    elif debt > 0:
        cost_of_debt_pre_tax = COST_OF_DEBT_BOUNDS[0]
        cost_of_debt_source = "default: 0.5% floor (no interest expense tag)"
        flags.append("cost_of_debt_default")
    else:
        cost_of_debt_pre_tax = 0.0
        cost_of_debt_source = "no debt outstanding"

    cost_of_equity = risk_free + beta * erp
    cost_of_debt = cost_of_debt_pre_tax * (1.0 - tax_rate)
    wacc = weight_equity * cost_of_equity + weight_debt * cost_of_debt

    inputs.extend(
        [
            _input("risk_free_rate", "Risk-free rate", risk_free, market.risk_free_source or "unknown"),
            _input("beta", "Beta", beta, beta_source, beta_detail),
            erp_input,
            _input(
                "cost_of_equity",
                "Cost of equity",
                cost_of_equity,
                "computed: rf + beta x ERP",
            ),
            _input(
                "cost_of_debt",
                "Cost of debt (after tax)",
                cost_of_debt,
                cost_of_debt_source,
                f"pre-tax {cost_of_debt_pre_tax:.2%}",
            ),
            _input(
                "tax_rate",
                "Tax rate",
                tax_rate,
                "default: 21% statutory" if tax_default else "sec: tax expense / pretax income",
            ),
            _input(
                "market_cap",
                "Market capitalisation",
                market_cap,
                market_cap_source,
            ),
            _input("weight_equity", "Equity weight", weight_equity, "computed: E / (E + D)"),
            _input("weight_debt", "Debt weight", weight_debt, "computed: D / (E + D)"),
        ]
    )

    return WaccBreakdown(
        ticker=company.ticker,
        wacc=wacc,
        cost_of_equity=cost_of_equity,
        cost_of_debt=cost_of_debt,
        weight_equity=weight_equity,
        weight_debt=weight_debt,
        market_cap=market_cap,
        price=market.price,
        as_of=market.as_of,
        inputs=inputs,
        flags=list(dict.fromkeys(flags)),
    )
