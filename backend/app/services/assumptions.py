"""Assumption review from the filing's claim ledger.

P1 pilot: for one engine assumption, select the claims that speak to it and say
whether they support or challenge the value the engine used.

The model only *selects* existing claims by id and proposes a range. It never
invents a quote, and it never writes a number into the valuation: applying a
suggestion is a user action that moves a slider.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app import llm
from app.services import filing

REVIEW_VERSION = "v3"
MAX_CLAIMS = 80
MAX_SELECTED = 6
MAX_QUOTE_CHARS = 320

SYSTEM_PROMPT = """You review whether a DCF assumption is supported by a company's 10-K.

Return ONLY JSON, no prose and no code fences:
{"stance":"supported|challenged|context_only",
 "lean":"higher|lower|neutral",
 "claim_ids":["id", "..."],
 "suggested_range":[low, high] or null,
 "rationale":"one or two sentences"}

Rules:
- "claim_ids" MUST be ids copied from the provided list. Never invent an id.
- Select the 1-6 claims that most directly speak to the assumption.
- Prefer forward-looking claims (guidance, outlook, planned capex, expected
  volume or pricing) over historical results. Historical growth alone is context.
- "suggested_range" is an annual growth rate as a decimal (0.02 means 2%).
  Propose a range when a claim states a rate, a target, or a direction with a
  magnitude ("mid single digit", "2-3%", "low teens"); otherwise null.
- stance "challenged" means the claims imply a materially different value than
  the engine used; "supported" means they broadly agree.
- "lean" is the direction the evidence points for this assumption relative to
  the engine value, independent of whether a range is available.
"""


def _digest(claims: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Flatten the tree into leaf claims, the ones carrying quotes."""
    leaves: list[dict[str, str]] = []

    def walk(nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            if len(leaves) >= MAX_CLAIMS:
                return
            if node.get("children"):
                walk(node["children"])
                continue
            quote = node.get("quote")
            if not isinstance(quote, str):
                continue
            leaves.append(
                {
                    "id": str(node.get("id")),
                    "section": str(node.get("section") or ""),
                    "statement": str(node.get("statement") or "")[:200],
                    "quote": quote[:MAX_QUOTE_CHARS],
                }
            )

    walk(claims)
    return leaves


def index_claims(claims: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}

    def walk(nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            index[str(node.get("id"))] = node
            walk(node.get("children") or [])

    walk(claims)
    return index


def _strip_json(text: str) -> dict[str, Any] | None:
    cleaned = re.sub(r"^```(?:json)?", "", text.strip()).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _parse_range(raw: Any) -> list[float] | None:
    if not isinstance(raw, list) or len(raw) != 2:
        return None
    try:
        low, high = float(raw[0]), float(raw[1])
    except (TypeError, ValueError):
        return None
    low = max(0.0, min(low, 0.5))
    high = max(0.0, min(high, 0.5))
    if high < low:
        low, high = high, low
    return [round(low, 4), round(high, 4)]


def review_growth(
    claims: list[dict[str, Any]],
    *,
    engine_value: float,
    engine_source: str,
) -> dict[str, Any] | None:
    digest = _digest(claims)
    if not digest:
        return None

    try:
        raw = llm.complete(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "assumption": "year-1 FCFF growth",
                            "engine_value": round(engine_value, 6),
                            "engine_source": engine_source,
                            "claims": digest,
                        }
                    ),
                },
            ]
        )
    except Exception:  # noqa: BLE001 - review is optional
        return None

    payload = _strip_json(raw)
    if payload is None:
        return None

    index = index_claims(claims)
    stance = str(payload.get("stance") or "context_only")
    if stance not in {"supported", "challenged", "context_only"}:
        stance = "context_only"

    lean = str(payload.get("lean") or "neutral").lower()
    if lean not in {"higher", "lower", "neutral"}:
        lean = "neutral"

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for claim_id in payload.get("claim_ids") or []:
        key = str(claim_id)
        if key in seen or key not in index:
            continue
        node = index[key]
        if not node.get("quote"):
            continue
        seen.add(key)
        selected.append(
            {
                "claim_id": key,
                "statement": str(node.get("statement") or ""),
                "quote": node.get("quote"),
                "section": node.get("section"),
                "verified": bool(node.get("verified")),
            }
        )
        if len(selected) >= MAX_SELECTED:
            break

    if not selected:
        return None

    return {
        "key": "growth_rate",
        "label": "Growth (year 1)",
        "engine_value": round(engine_value, 6),
        "engine_source": engine_source,
        "stance": stance,
        "lean": lean,
        "suggested_range": _parse_range(payload.get("suggested_range")),
        "rationale": str(payload.get("rationale") or "")[:400] or None,
        "evidence": selected,
    }


def cache_path(accession: str):
    return filing.cache_path(accession).with_name(f"{accession}.assumptions.json")


def load_cached(accession: str) -> dict[str, Any] | None:
    path = cache_path(accession)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    return payload if payload.get("version") == REVIEW_VERSION else None


def save_cached(accession: str, payload: dict[str, Any]) -> None:
    cache_path(accession).write_text(json.dumps(payload))
