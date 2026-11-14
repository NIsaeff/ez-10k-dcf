"""Assumption review: claim selection, range parsing, cache. No LLM, no network."""

import json

from app.services import assumptions

CLAIMS = [
    {
        "id": "p0",
        "statement": "Growth outlook",
        "children": [
            {
                "id": "p0-c0",
                "statement": "Management guides to 3% growth",
                "quote": "We expect volume growth of approximately 3% in 2026.",
                "section": "Item 7",
                "verified": True,
                "children": [],
            },
            {
                "id": "p0-c1",
                "statement": "Volume was flat",
                "quote": "Unit case volume was flat for the year.",
                "section": "Item 7",
                "verified": True,
                "children": [],
            },
        ],
    }
]


def _llm(payload):
    return lambda messages: json.dumps(payload)


def test_review_selects_valid_claims_and_range(monkeypatch) -> None:
    monkeypatch.setattr(
        assumptions.llm,
        "complete",
        _llm(
            {
                "stance": "challenged",
                "claim_ids": ["p0-c0", "does-not-exist"],
                "suggested_range": [0.02, 0.03],
                "rationale": "Guidance is above the engine's estimate.",
            }
        ),
    )

    review = assumptions.review_growth(
        CLAIMS, engine_value=0.012, engine_source="historical_fcff_cagr"
    )

    assert review is not None
    assert review["stance"] == "challenged"
    assert [item["claim_id"] for item in review["evidence"]] == ["p0-c0"]
    assert review["suggested_range"] == [0.02, 0.03]
    assert review["engine_value"] == 0.012


def test_review_normalises_reversed_range(monkeypatch) -> None:
    monkeypatch.setattr(
        assumptions.llm,
        "complete",
        _llm({"stance": "supported", "claim_ids": ["p0-c0"], "suggested_range": [0.05, 0.02]}),
    )

    review = assumptions.review_growth(
        CLAIMS, engine_value=0.01, engine_source="historical_fcff_cagr"
    )

    assert review is not None
    assert review["suggested_range"] == [0.02, 0.05]


def test_review_drops_invalid_range(monkeypatch) -> None:
    monkeypatch.setattr(
        assumptions.llm,
        "complete",
        _llm({"stance": "context_only", "claim_ids": ["p0-c0"], "suggested_range": ["x", 2]}),
    )

    review = assumptions.review_growth(
        CLAIMS, engine_value=0.01, engine_source="historical_fcff_cagr"
    )

    assert review is not None
    assert review["suggested_range"] is None


def test_review_requires_quoted_claims(monkeypatch) -> None:
    monkeypatch.setattr(
        assumptions.llm,
        "complete",
        _llm({"stance": "supported", "claim_ids": ["p0-c0"]}),
    )

    review = assumptions.review_growth(
        [{"id": "p0-c0", "statement": "no quote", "children": []}],
        engine_value=0.01,
        engine_source="historical_fcff_cagr",
    )

    assert review is None


def test_review_survives_model_failure(monkeypatch) -> None:
    def boom(messages):
        raise RuntimeError("provider down")

    monkeypatch.setattr(assumptions.llm, "complete", boom)

    assert (
        assumptions.review_growth(
            CLAIMS, engine_value=0.01, engine_source="historical_fcff_cagr"
        )
        is None
    )


def test_review_cache_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(assumptions.filing.settings, "data_dir", tmp_path)

    payload = {
        "version": assumptions.REVIEW_VERSION,
        "reviews": [{"key": "growth_rate", "stance": "challenged"}],
        "flags": [],
    }
    assumptions.save_cached("0000000000-25-000001", payload)

    assert assumptions.load_cached("0000000000-25-000001") == payload

    assumptions.save_cached(
        "0000000000-25-000001", {"version": "old", "reviews": []}
    )
    assert assumptions.load_cached("0000000000-25-000001") is None
