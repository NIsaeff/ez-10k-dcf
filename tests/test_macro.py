"""Deterministic FRED macro layer: cache, freshness, provenance, fallback.

The autouse fixture in conftest blanks the API key and points the cache at a
tmp dir, so nothing here touches the network unless a test patches ``_fetch``.
"""

import json
import time
from datetime import UTC, datetime

import pytest

from app.config import settings
from app.schemas import MacroInput
from app.services import macro, market

ROWS = [
    {"date": "2026-11-12", "value": "5.10"},
    {"date": "2026-11-11", "value": "."},
]


def _today() -> str:
    return datetime.now(tz=UTC).date().isoformat()


def _freeze_fetch(monkeypatch, rows=ROWS) -> list[str]:
    calls: list[str] = []

    def fake_fetch(series_id: str, **_kwargs) -> list[dict]:
        calls.append(series_id)
        return rows

    monkeypatch.setattr(macro, "_fetch", fake_fetch)
    return calls


# --- observation parsing ----------------------------------------------------


def test_latest_skips_fred_missing_value_markers() -> None:
    assert macro._latest(ROWS) == (5.10, "2026-11-12")


def test_latest_returns_none_when_everything_is_missing() -> None:
    assert macro._latest([{"date": "2026-11-12", "value": "."}]) is None


# --- cache ------------------------------------------------------------------


def test_observations_are_cached_on_disk(monkeypatch) -> None:
    calls = _freeze_fetch(monkeypatch)

    first, _, stale = macro.observations("DGS10", now=1000.0)
    again, _, stale_again = macro.observations("DGS10", now=1001.0)

    assert calls == ["DGS10"]
    assert first == again == ROWS
    assert stale is False and stale_again is False
    assert (macro.CACHE_DIR / "DGS10.json").exists()


def test_stale_cache_is_served_when_the_refresh_fails(monkeypatch) -> None:
    path = macro.CACHE_DIR / "DGS10.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fetched_at": 0, "observations": ROWS}))
    monkeypatch.setattr(
        macro, "_fetch", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down"))
    )

    rows, _, stale = macro.observations("DGS10", now=macro.CACHE_TTL_SECONDS + 1)

    assert rows == ROWS
    assert stale is True


# --- inputs -----------------------------------------------------------------


def test_input_for_marks_old_observations_stale(monkeypatch) -> None:
    monkeypatch.setattr(settings, "fred_api_key", "key")
    monkeypatch.setattr(macro, "_fetch", lambda *a, **k: [{"date": "2020-01-01", "value": "1.5"}])

    item = macro.input_for("risk_free", now=time.time())

    assert item is not None
    assert item.stale is True
    assert item.source == "fred"
    assert item.url == "https://fred.stlouisfed.org/series/DGS10"


def test_input_for_returns_none_without_a_key(monkeypatch) -> None:
    assert macro.input_for("risk_free") is None


# --- snapshot ---------------------------------------------------------------


def test_snapshot_is_complete_when_every_series_is_fresh(monkeypatch) -> None:
    monkeypatch.setattr(settings, "fred_api_key", "key")
    fresh = [{"date": _today(), "value": "1.0"}]
    monkeypatch.setattr(macro, "_fetch", lambda *a, **k: fresh)

    snap = macro.snapshot()

    assert snap.status == "complete"
    assert snap.flags == []
    assert {item.role for item in snap.inputs} == {
        "risk_free",
        "cpi",
        "real_gdp",
        "unemployment",
    }


def test_snapshot_is_absent_without_fred() -> None:
    snap = macro.snapshot()

    assert snap.status == "absent"
    assert snap.inputs == []
    assert "macro_risk_free_missing" in snap.flags


def test_snapshot_degrades_with_a_fallback(monkeypatch) -> None:
    monkeypatch.setattr(settings, "fred_api_key", "key")
    monkeypatch.setattr(
        macro, "_fetch", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down"))
    )
    fallback = MacroInput(
        role="risk_free",
        series="^TNX",
        label="10-year Treasury (Yahoo)",
        value=0.051,
        units="Ratio",
        observation_date=_today(),
        source="yahoo",
    )

    snap = macro.snapshot(risk_free_fallback=fallback)

    assert snap.status == "degraded"
    assert "risk_free_fallback" in snap.flags
    assert snap.inputs[0].series == "^TNX"


# --- risk-free preference ---------------------------------------------------


def _fred(value: float = 5.10, *, stale: bool = False, source: str = "fred") -> MacroInput:
    return MacroInput(
        role="risk_free",
        series="DGS10",
        label="10-year Treasury constant maturity",
        value=value,
        units="Percent",
        observation_date="2026-11-12",
        source=source,
        stale=stale,
    )


def test_risk_free_prefers_fred(monkeypatch) -> None:
    monkeypatch.setattr(macro, "risk_free", lambda: _fred())

    value, source = market.risk_free_with_source()

    assert value == pytest.approx(0.051)
    assert source == "fred: DGS10 2026-11-12"


def test_risk_free_falls_back_to_yahoo(monkeypatch) -> None:
    monkeypatch.setattr(macro, "risk_free", lambda: None)
    monkeypatch.setattr(market, "risk_free_rate", lambda: 0.042)

    assert market.risk_free_with_source() == (0.042, "yahoo: ^TNX 10y close")


def test_fresh_yahoo_beats_stale_fred(monkeypatch) -> None:
    monkeypatch.setattr(macro, "risk_free", lambda: _fred(stale=True))
    monkeypatch.setattr(market, "risk_free_rate", lambda: 0.042)

    assert market.risk_free_with_source() == (0.042, "yahoo: ^TNX 10y close")


def test_stale_fred_beats_having_nothing(monkeypatch) -> None:
    monkeypatch.setattr(macro, "risk_free", lambda: _fred(stale=True))
    monkeypatch.setattr(market, "risk_free_rate", lambda: None)

    value, source = market.risk_free_with_source()

    assert value == pytest.approx(0.051)
    assert source.endswith("(stale)")


def test_market_inputs_flag_the_yahoo_fallback(monkeypatch) -> None:
    monkeypatch.setattr(macro, "risk_free", lambda: None)
    monkeypatch.setattr(market, "risk_free_rate", lambda: 0.042)
    monkeypatch.setattr(market, "quote_summary", lambda t: ({}, False))
    monkeypatch.setattr(market, "computed_beta", lambda t: (None, 0, None))
    monkeypatch.setattr(market, "chart", lambda *a, **k: ({}, False))

    inputs = market.market_inputs("KO")

    assert inputs.risk_free_rate == pytest.approx(0.042)
    assert inputs.risk_free_source == "yahoo: ^TNX 10y close"
    assert "risk_free_fallback_yahoo" in inputs.flags


# --- valuation wiring -------------------------------------------------------


def test_valuation_carries_the_macro_snapshot(monkeypatch) -> None:
    from app.services import valuation
    from tests.conftest import company_from_fixture

    monkeypatch.setattr(
        valuation.macro,
        "snapshot",
        lambda **_: macro.MacroSnapshot(status="complete", as_of="2026-11-12"),
    )

    result = valuation.analyze_from_company(company_from_fixture("KO"))

    assert result.macro.status == "complete"
    assert result.macro.as_of == "2026-11-12"
