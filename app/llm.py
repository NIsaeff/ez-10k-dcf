from __future__ import annotations

import json
import time
from functools import lru_cache
from typing import Any

from openai import OpenAI

from app.config import settings
from app.schemas import Proposal, ValuationResult, WizardContext
from app.services import fred_mcp, wizard_proposals

CHAT_SYSTEM_PROMPT = (
    "You are EZ-10k, a concise assistant for 10-K financial analysis and DCF "
    "valuation. If the user asks for a valuation, tell them to include a supported "
    "ticker (AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, KO, PWR). Do not invent "
    "financial figures."
)

WIZARD_SYSTEM_PROMPT = (
    " You can also drive the DCF wizard. The current wizard state is in the JSON "
    "context. When the user asks to change an assumption, or asks a what-if, call "
    "propose_wizard_change with 1-5 changes; when they ask to open a company, a tab "
    "or a filing claim, call propose_navigation. Call "
    "wizard_explain_assumption first when the proposal rests on filing language. "
    "Never say a change was applied: the human must confirm it. Set confidence "
    "0-1 to reflect how well-sourced the change is (direct quote or FRED "
    "observation >= 0.9, general reasoning 0.6-0.8). Units: growth, tax, capex, "
    "wacc and terminal are percentages (4 means 4%); shares are millions; years is "
    "an integer."
)

WIZARD_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "propose_wizard_change",
            "description": (
                "Propose changes to the DCF wizard. Does NOT apply them; the user "
                "confirms in the interface."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "rationale": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "changes": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 5,
                        "items": {
                            "type": "object",
                            "properties": {
                                "key": {
                                    "type": "string",
                                    "enum": [
                                        "growth",
                                        "tax",
                                        "capex",
                                        "wacc",
                                        "terminal",
                                        "years",
                                        "shares",
                                        "model",
                                    ],
                                },
                                "value": {"type": ["number", "string"]},
                            },
                            "required": ["key", "value"],
                        },
                    },
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "label": {"type": "string"},
                                "ref": {"type": "string"},
                                "quote": {"type": "string"},
                            },
                        },
                    },
                },
                "required": ["title", "rationale", "confidence", "changes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_navigation",
            "description": (
                "Propose opening a company, a wizard tab or a filing claim. The "
                "user confirms before the workspace moves."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "rationale": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "ticker": {"type": "string"},
                    "tab": {"type": "string", "enum": ["fcff", "wacc", "dcf", "filing"]},
                    "claim_id": {"type": "string"},
                },
                "required": ["title", "rationale"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wizard_explain_assumption",
            "description": "Read the filing review (quotes, stance) for an assumption.",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string", "enum": ["growth"]}},
                "required": ["key"],
            },
        },
    },
]

FRED_SYSTEM_PROMPT = (
    " You also have FRED macro tools (fred_search, fred_browse, fred_get_series). "
    "Call them for Treasury yields, inflation, GDP, unemployment and similar "
    "series instead of guessing. Quote the series ID and its units, and mention "
    "the observation date rather than implying a value is live."
)

MAX_TOOL_ROUNDS = 4

NARRATION_SYSTEM_PROMPT = (
    "You are a financial analyst answering a valuation question in chat. "
    "Use ONLY the values in the JSON. Never calculate, change, or invent a number; "
    "quote every figure using the strings in `display` and `assumptions`. "
    "Reply in plain prose, 2-4 short paragraphs, and cover:\n"
    "1. The result: value per share, enterprise value, equity value.\n"
    "2. How it was derived, in words: free cash flow to the firm is after-tax EBIT "
    "plus D&A minus CapEx minus the change in net working capital; it is projected "
    "over the stated horizon along the stated growth path, discounted at the WACC "
    "shown, with a Gordon-growth terminal value; equity value is enterprise value "
    "minus net debt, and per-share value divides equity by diluted shares.\n"
    "3. The assumptions that drive it and where each came from: growth (and whether "
    "it is the historical FCFF CAGR or an override), sequential/constant path, "
    "terminal growth, WACC and its source, the normalized FCFF base and why years "
    "are excluded, tax rate, share count.\n"
    "4. Sources, named explicitly: the latest 10-K from SEC EDGAR (form, fiscal "
    "year, filed date, accession), the SEC XBRL companyfacts feed behind the "
    "figures, and Yahoo Finance for market inputs (price, beta, risk-free) when "
    "used. Say the cost of debt comes from the filing's interest expense.\n"
    "5. One caveat from `flags`, then the disclaimer text.\n"
    "Do not output tables, cards, or dashboards; the interface links to the DCF "
    "Wizard for the full breakdown."
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
    filing = result.filing
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
        "method": {
            "fcff": "EBIT x (1 - tax) + D&A - CapEx - change in net working capital",
            "projection": (
                f"{assumptions.projection_years}-year projection, "
                f"{assumptions.growth_model} growth from "
                f"{assumptions.growth_rate:.1%} to "
                f"{assumptions.terminal_growth_rate:.1%}"
            ),
            "discounting": f"discounted at {assumptions.wacc:.1%} ({assumptions.wacc_source})",
            "terminal_value": "Gordon growth on the final year's FCFF",
            "bridge": "enterprise value minus net debt = equity; equity / diluted shares = per share",
        },
        "assumptions": {
            "growth": f"{assumptions.growth_rate:.1%} ({assumptions.growth_source})",
            "growth_model": assumptions.growth_model,
            "terminal_growth": f"{assumptions.terminal_growth_rate:.1%}",
            "wacc": f"{assumptions.wacc:.1%} ({assumptions.wacc_source})",
            "fcff_base": f"{_compact(assumptions.fcff_base)} ({assumptions.fcff_base_source})",
            "tax_rate": f"{assumptions.tax_rate:.1%} ({assumptions.tax_rate_source})",
            "share_count": assumptions.share_count_source,
            "net_debt": assumptions.net_debt_treatment,
        },
        "filing": {
            "form": filing.form,
            "fiscal_year_end": filing.fiscal_year_end,
            "filed": filing.filed,
            "accession": filing.accession_number,
            "url": filing.url,
        },
        "sources": result.sources,
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


def chat_reply(
    messages: list[dict[str, str]],
    context: WizardContext | None = None,
) -> tuple[str, list[dict[str, Any]], list[Proposal]]:
    """Answer a chat turn with FRED and wizard tools.

    Returns (reply, tool trace, proposals). Proposals are never applied here.
    """
    limited = messages[-20:]
    system = CHAT_SYSTEM_PROMPT
    tools: list[dict[str, Any]] = list(WIZARD_TOOLS)

    if fred_mcp.configured():
        try:
            tools.extend(fred_mcp.openai_tools())
            system += FRED_SYSTEM_PROMPT
        except fred_mcp.FredMCPError:
            # A broken MCP server must not take the whole chat down.
            pass

    wizard_context = context or WizardContext()
    system += WIZARD_SYSTEM_PROMPT
    system += "\n\nCURRENT WIZARD STATE (JSON): " + json.dumps(
        wizard_context.model_dump()
    )

    conversation: list[dict[str, Any]] = [{"role": "system", "content": system}, *limited]
    return _tool_loop(conversation, tools, wizard_context)


def _tool_loop(
    conversation: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    context: WizardContext,
) -> tuple[str, list[dict[str, Any]], list[Proposal]]:
    trace: list[dict[str, Any]] = []
    proposals: list[Proposal] = []

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            message = _complete_with_tools(conversation, tools)
        except Exception:  # noqa: BLE001 - proxy may reject tools; answer without
            break

        calls = list(message.tool_calls or [])
        if not calls:
            return (message.content or ""), trace, proposals

        conversation.append(_assistant_turn(message.content, calls))
        for call in calls:
            turn, step = _tool_turn(call, context, proposals)
            conversation.append(turn)
            trace.append(step)

    return complete(conversation), trace, proposals


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


def _tool_turn(
    call: Any,
    context: WizardContext,
    proposals: list[Proposal],
) -> tuple[dict[str, Any], dict[str, Any]]:
    arguments: dict[str, Any] = {}
    status = "ok"
    started = time.perf_counter()
    name = call.function.name

    try:
        parsed = json.loads(call.function.arguments or "{}")
        if isinstance(parsed, dict):
            arguments = parsed

        if name == "propose_wizard_change":
            proposal = wizard_proposals.build_proposal(context, arguments)
            proposals.append(proposal)
            content = json.dumps(
                {
                    "status": "recorded",
                    "proposal_id": proposal.id,
                    "note": "The user must confirm before it is applied.",
                }
            )
        elif name == "propose_navigation":
            proposal = wizard_proposals.build_navigation(context, arguments)
            proposals.append(proposal)
            content = json.dumps(
                {
                    "status": "recorded",
                    "proposal_id": proposal.id,
                    "note": "The user must confirm before the workspace moves.",
                }
            )
        elif name == "wizard_explain_assumption":
            content = wizard_proposals.explain(
                context, str(arguments.get("key") or "growth")
            )
        else:
            content = fred_mcp.call_tool(name, arguments)
    except Exception as exc:  # noqa: BLE001 - report the failure to the model
        status = "error"
        content = f"ERROR calling {name}: {exc}"

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
    assumptions = result.assumptions
    filing = result.filing
    flags = ", ".join(result.flags) if result.flags else "none"
    return (
        f"{result.company_name} ({result.ticker}) is worth about "
        f"${valuation.value_per_share:,.2f} per share under this DCF, with an "
        f"enterprise value of ${valuation.enterprise_value / 1e9:,.1f}B and equity "
        f"value of ${valuation.equity_value / 1e9:,.1f}B.\n\n"
        "Method: free cash flow to the firm (after-tax EBIT plus D&A minus CapEx "
        f"minus the change in net working capital) is projected for "
        f"{assumptions.projection_years} years with {assumptions.growth_model} growth from "
        f"{assumptions.growth_rate:.1%} to {assumptions.terminal_growth_rate:.1%}, "
        f"discounted at a {assumptions.wacc:.1%} WACC with a Gordon-growth terminal "
        "value; net debt is subtracted from enterprise value and the result is "
        "divided by diluted shares.\n\n"
        f"Inputs: normalized FCFF base {_compact(assumptions.fcff_base)} "
        f"({assumptions.fcff_base_source}), tax {assumptions.tax_rate:.1%} "
        f"({assumptions.tax_rate_source}), shares from "
        f"{assumptions.share_count_source}. Sources: the latest {filing.form} "
        f"(FY ending {filing.fiscal_year_end}, filed {filing.filed}, accession "
        f"{filing.accession_number}) from SEC EDGAR, figures from SEC XBRL "
        "companyfacts. Flags: "
        f"{flags}. {result.disclaimer}"
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
