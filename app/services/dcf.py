"""Deterministic DCF math.

No network, no LLM, no database. Given the same inputs, the output is identical.
See docs/valuation-spec.md for the formulas this implements.
"""

from app.schemas import ProjectionYear, ValuationSummary, YearFinancials

DEFAULT_TAX_RATE = 0.21
DEFAULT_TERMINAL_GROWTH = 0.025
DEFAULT_GROWTH = 0.05
DEFAULT_PROJECTION_YEARS = 5


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def effective_tax_rate(tax_expense: float | None, pretax_income: float | None) -> tuple[float, bool]:
    """Return (tax_rate, used_default)."""
    if tax_expense is None or pretax_income is None or pretax_income <= 0:
        return DEFAULT_TAX_RATE, True
    return clamp(tax_expense / pretax_income, 0.0, 0.35), False


def build_history(raw_years: list[dict]) -> tuple[list[YearFinancials], list[str]]:
    """Turn raw annual rows into FCFF history.

    Each raw row needs: fiscal_year, ebit, depreciation_amortization,
    capital_expenditures. Optional: revenue, pretax_income, tax_expense,
    current_assets, current_liabilities.
    """
    flags: list[str] = []
    rows = [
        row
        for row in raw_years
        if row.get("ebit") is not None
        and row.get("depreciation_amortization") is not None
        and row.get("capital_expenditures") is not None
    ]
    rows.sort(key=lambda row: row["fiscal_year"])
    rows = rows[-5:]

    history: list[YearFinancials] = []
    previous_nwc: float | None = None
    used_default_tax = False
    used_nwc_fallback = False

    for row in rows:
        tax_rate, defaulted = effective_tax_rate(
            row.get("tax_expense"), row.get("pretax_income")
        )
        used_default_tax = used_default_tax or defaulted

        current_assets = row.get("current_assets")
        current_liabilities = row.get("current_liabilities")
        nwc: float | None = None
        if current_assets is not None and current_liabilities is not None:
            nwc = current_assets - current_liabilities

        if nwc is None:
            change_in_nwc = 0.0
            used_nwc_fallback = True
        elif previous_nwc is None:
            change_in_nwc = 0.0
        else:
            change_in_nwc = nwc - previous_nwc

        if nwc is not None:
            previous_nwc = nwc

        fcff = (
            row["ebit"] * (1.0 - tax_rate)
            + row["depreciation_amortization"]
            - row["capital_expenditures"]
            - change_in_nwc
        )

        history.append(
            YearFinancials(
                fiscal_year=int(row["fiscal_year"]),
                revenue=row.get("revenue"),
                ebit=row["ebit"],
                pretax_income=row.get("pretax_income"),
                tax_expense=row.get("tax_expense"),
                depreciation_amortization=row["depreciation_amortization"],
                capital_expenditures=row["capital_expenditures"],
                change_in_nwc=change_in_nwc if nwc is not None else None,
                fcff=fcff,
            )
        )

    if used_default_tax:
        flags.append("tax_rate_default")
    if used_nwc_fallback:
        flags.append("nwc_unavailable")
    if len(history) < 3:
        flags.append("history_lt_3y")

    return history, flags


def historical_growth(history: list[YearFinancials], base_fcff: float) -> tuple[float, str, list[str]]:
    flags: list[str] = []
    if len(history) < 2:
        return DEFAULT_GROWTH, "default", ["growth_default"]

    oldest = history[0].fcff
    if oldest <= 0 or base_fcff <= 0:
        return DEFAULT_GROWTH, "default", ["growth_default"]

    periods = len(history) - 1
    growth = (base_fcff / oldest) ** (1.0 / periods) - 1.0
    growth = clamp(growth, -0.20, 0.30)
    return growth, "historical_fcff_cagr", flags


def select_fcff_base(history: list[YearFinancials]) -> tuple[float, str, list[str]]:
    """Use a normalized base: mean of positive FCFF over the last up to 5 years,
    excluding values outside 0.5x-2x the median.

    One capex or working-capital spike should not dominate the whole valuation
    (KO/GOOGL 2025 are examples). If there are no positive years, fall back to the
    latest value and flag it.
    """
    window = [year.fcff for year in history[-5:] if year.fcff > 0]
    if window:
        ordered = sorted(window)
        median = ordered[len(ordered) // 2]
        filtered = [value for value in window if 0.5 * median <= value <= 2.0 * median]
        chosen = filtered or window
        return sum(chosen) / len(chosen), "normalized_average", ["fcff_base_normalized"]

    positive = [year.fcff for year in history if year.fcff > 0]
    if positive:
        return (
            sum(positive) / len(positive),
            "positive_average",
            ["fcff_base_positive_avg"],
        )

    return history[-1].fcff, "latest", ["negative_fcff"]


def project_fcff(
    base_fcff: float,
    growth_rate: float,
    terminal_growth_rate: float,
    base_year: int,
    wacc: float,
    years: int = DEFAULT_PROJECTION_YEARS,
) -> list[ProjectionYear]:
    projection: list[ProjectionYear] = []
    fcff = base_fcff
    for index in range(1, years + 1):
        if years > 1:
            growth = growth_rate + (terminal_growth_rate - growth_rate) * (index - 1) / (years - 1)
        else:
            growth = growth_rate
        fcff = fcff * (1.0 + growth)
        discount_factor = 1.0 / (1.0 + wacc) ** index
        projection.append(
            ProjectionYear(
                year=base_year + index,
                fcff=fcff,
                discount_factor=discount_factor,
                present_value=fcff * discount_factor,
            )
        )
    return projection


def terminal_value(final_fcff: float, terminal_growth_rate: float, wacc: float) -> float:
    if wacc <= terminal_growth_rate:
        raise ValueError("WACC must be greater than terminal growth rate")
    return final_fcff * (1.0 + terminal_growth_rate) / (wacc - terminal_growth_rate)


def build_valuation(
    *,
    projection: list[ProjectionYear],
    terminal_growth_rate: float,
    wacc: float,
    total_debt: float,
    cash_and_equivalents: float,
    shares_outstanding: float,
) -> tuple[ValuationSummary, list[str]]:
    flags: list[str] = []
    if not projection:
        raise ValueError("projection cannot be empty")
    if shares_outstanding <= 0:
        raise ValueError("shares outstanding must be positive")

    tv = terminal_value(projection[-1].fcff, terminal_growth_rate, wacc)
    discount_factor = projection[-1].discount_factor
    pv_terminal = tv * discount_factor
    enterprise_value = sum(year.present_value for year in projection) + pv_terminal

    net_debt = total_debt - cash_and_equivalents
    equity_value = enterprise_value - net_debt
    value_per_share = equity_value / shares_outstanding
    if equity_value < 0:
        flags.append("negative_equity")

    summary = ValuationSummary(
        terminal_value=tv,
        present_value_terminal=pv_terminal,
        enterprise_value=enterprise_value,
        total_debt=total_debt,
        cash_and_equivalents=cash_and_equivalents,
        net_debt=net_debt,
        equity_value=equity_value,
        shares_outstanding=shares_outstanding,
        value_per_share=value_per_share,
    )
    return summary, flags
