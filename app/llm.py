from __future__ import annotations

import json
from functools import lru_cache

from openai import OpenAI

from app.config import settings
from app.schemas import ValuationResult

CHAT_SYSTEM_PROMPT = (
    "You are EZ-10k, a concise assistant for 10-K financial analysis and DCF "
    "valuation. If the user asks for a valuation, tell them to include a supported "
    "ticker (AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, KO, PWR). Do not invent "
    "financial figures."
)

NARRATION_SYSTEM_PROMPT = (
    "You are a financial analyst writing a short summary of a completed DCF. "
    "Use ONLY the values in the JSON. Never calculate, change, or invent a number. "
    "Use the strings in `display` verbatim for every number; never print a raw "
    "decimal. Write at most 3 sentences: company/ticker, value per share, enterprise "
    "value, WACC, terminal growth, the fiscal year of the filing, and one caveat from "
    "flags. End with the disclaimer text. "
)


def _compact(value: float) -> str:
    sign = "-" if value < 0 else ""
    absolute = abs(value)
    if absolute >= 1e12:
        return f"{sign}${absolute / 1e12:,.2f}T"
    if absolute >= 1e9:
        return f"{sign}${absolute / 1e9:,.1f}B"
    if absolute >= 1e6:
        return f"{sign}${absolute / 1e6:,.0f}M"
    return f"{sign}${absolute:,.0f}"


def _display(result: ValuationResult) -> dict[str, object]:
    summary = result.valuation
    assumptions = result.assumptions
    return {
        "company_name": result.company_name,
        "ticker": result.ticker,
        "fiscal_year": result.history[-1].fiscal_year,
        "value_per_share": f"${summary.value_per_share:,.2f}",
        "enterprise_value": _compact(summary.enterprise_value),
        "equity_value": _compact(summary.equity_value),
        "net_debt": _compact(summary.net_debt),
        "wacc": f"{assumptions.wacc:.1%}",
        "terminal_growth": f"{assumptions.terminal_growth_rate:.1%}",
        "flags": result.flags,
        "disclaimer": result.disclaimer,
    }


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to .env.")
    return OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout=30.0,
    )


def complete(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float | None = None,
) -> str:
    """Run one chat completion and return the assistant text.

    Temperature is omitted unless explicitly requested: some reasoning models
    on the LiteLLM proxy reject temperature=0 while reasoning is active.
    """
    kwargs: dict[str, object] = {
        "model": model or settings.llm_model,
        "messages": messages,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature

    response = get_client().chat.completions.create(**kwargs)
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("LLM returned an empty response")
    return content


def chat_reply(messages: list[dict[str, str]]) -> str:
    limited = messages[-20:]
    return complete(
        [{"role": "system", "content": CHAT_SYSTEM_PROMPT}, *limited]
    )


def _fallback_narration(result: ValuationResult) -> str:
    valuation = result.valuation
    flags = ", ".join(result.flags) if result.flags else "none"
    return (
        f"{result.company_name} ({result.ticker}) is worth about "
        f"${valuation.value_per_share:,.2f} per share under this DCF. "
        f"Enterprise value is ${valuation.enterprise_value / 1e9:,.1f}B, using a "
        f"{result.assumptions.wacc:.1%} WACC and "
        f"{result.assumptions.terminal_growth_rate:.1%} terminal growth, based on the "
        f"FY{result.history[-1].fiscal_year} 10-K. Flags: {flags}. "
        "Illustrative, not investment advice."
    )


def narrate_valuation(result: ValuationResult) -> str:
    payload = {
        "display": _display(result),
        "details": result.model_dump(),
    }
    try:
        return complete(
            [
                {"role": "system", "content": NARRATION_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload)},
            ]
        )
    except Exception:  # noqa: BLE001 - narration must never break the response
        # Narration is non-critical; the computed result is the source of truth.
        return _fallback_narration(result)
