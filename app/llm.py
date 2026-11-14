from __future__ import annotations

import json
import time
from functools import lru_cache
from typing import Any

from openai import OpenAI

from app.config import settings
from app.schemas import ValuationResult
from app.services import fred_mcp

CHAT_SYSTEM_PROMPT = (
    "You are EZ-10k, a concise assistant for 10-K financial analysis and DCF "
    "valuation. If the user asks for a valuation, tell them to include a supported "
    "ticker (AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, KO, PWR). Do not invent "
    "financial figures."
)

FRED_SYSTEM_PROMPT = (
    " You also have FRED macro tools (fred_search, fred_browse, fred_get_series). "
    "Call them for Treasury yields, inflation, GDP, unemployment and similar "
    "series instead of guessing. Quote the series ID and its units, and mention "
    "the observation date rather than implying a value is live."
)

MAX_TOOL_ROUNDS = 4

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


def chat_reply(messages: list[dict[str, str]]) -> tuple[str, list[dict[str, Any]]]:
    """Answer a chat turn, using FRED MCP tools when they are configured.

    Returns the reply text plus the tool trace (one entry per MCP call) so the
    UI can show what the assistant actually looked up.
    """
    limited = messages[-20:]
    system = CHAT_SYSTEM_PROMPT
    tools: list[dict[str, Any]] = []

    if fred_mcp.configured():
        try:
            tools = fred_mcp.openai_tools()
            system += FRED_SYSTEM_PROMPT
        except fred_mcp.FredMCPError:
            # A broken MCP server must not take the whole chat down.
            tools = []

    conversation: list[dict[str, Any]] = [{"role": "system", "content": system}, *limited]
    if not tools:
        return complete(conversation), []
    return _tool_loop(conversation, tools)


def _tool_loop(
    conversation: list[dict[str, Any]], tools: list[dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    trace: list[dict[str, Any]] = []

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            message = _complete_with_tools(conversation, tools)
        except Exception:  # noqa: BLE001 - proxy may reject tools; answer without
            break

        calls = list(message.tool_calls or [])
        if not calls:
            return (message.content or ""), trace

        conversation.append(_assistant_turn(message.content, calls))
        for call in calls:
            turn, step = _tool_turn(call)
            conversation.append(turn)
            trace.append(step)

    return complete(conversation), trace


def _complete_with_tools(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]]
) -> Any:
    response = get_client().chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )
    return response.choices[0].message


def _assistant_turn(content: str | None, calls: list[Any]) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": content or "",
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments or "{}",
                },
            }
            for call in calls
        ],
    }


def _tool_turn(call: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    arguments: dict[str, Any] = {}
    status = "ok"
    started = time.perf_counter()

    try:
        parsed = json.loads(call.function.arguments or "{}")
        if isinstance(parsed, dict):
            arguments = parsed
        content = fred_mcp.call_tool(call.function.name, arguments)
    except Exception as exc:  # noqa: BLE001 - report the failure to the model
        status = "error"
        content = f"ERROR calling {call.function.name}: {exc}"

    step = {
        "tool": call.function.name,
        "input": arguments,
        "status": status,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "output": content,
    }
    return {"role": "tool", "tool_call_id": call.id, "content": content}, step


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
