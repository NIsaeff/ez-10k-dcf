import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import valuation
from app.services.financials import InsufficientData
from tests.conftest import company_from_fixture

client = TestClient(app)

KO_RESULT = valuation.analyze_from_company(company_from_fixture("KO"))


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "KO" in body["supported_tickers"]


def test_analyze_supported_ticker(monkeypatch) -> None:
    monkeypatch.setattr(valuation, "analyze", lambda ticker, overrides=None, **_: KO_RESULT)
    response = client.post("/api/analyze/ko")
    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "KO"
    assert body["valuation"]["value_per_share"] > 0


def test_analyze_unsupported_ticker() -> None:
    response = client.post("/api/analyze/ZZZ")
    assert response.status_code == 422
    assert response.json()["error"] == "unsupported_ticker"


def test_analyze_insufficient_data(monkeypatch) -> None:
    def boom(ticker: str, overrides=None, **_) -> None:
        raise InsufficientData(ticker, ["shares_outstanding"])

    monkeypatch.setattr(valuation, "analyze", boom)
    response = client.post("/api/analyze/KO")
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "insufficient_data"
    assert body["missing_fields"] == ["shares_outstanding"]


def test_chat_values_a_ticker(monkeypatch) -> None:
    monkeypatch.setattr(valuation, "analyze", lambda ticker, overrides=None, **_: KO_RESULT)
    monkeypatch.setattr(
        "app.main.llm.narrate_valuation",
        lambda result: "KO is worth about $31.70 per share.",
    )
    response = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "value KO"}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["valuation"]["ticker"] == "KO"
    assert "$31.70" in body["reply"]


def test_chat_plain_message_uses_llm(monkeypatch) -> None:
    monkeypatch.setattr("app.main.llm.chat_reply", lambda messages: "Hello there.")
    response = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 200
    assert response.json() == {"reply": "Hello there.", "valuation": None}


def test_chat_insufficient_data_is_friendly(monkeypatch) -> None:
    def boom(ticker: str, overrides=None, **_) -> None:
        raise InsufficientData(ticker, ["cash_and_equivalents"])

    monkeypatch.setattr(valuation, "analyze", boom)
    response = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "value KO"}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["valuation"] is None
    assert "cash_and_equivalents" in body["reply"]


# --- SPA fallback -----------------------------------------------------------
# Skipped on a clean checkout: routes are registered at import time only when
# frontend/dist exists.

needs_dist = pytest.mark.skipif(
    not settings.frontend_dist.is_dir(),
    reason="frontend/dist not built",
)


@needs_dist
def test_client_route_serves_index() -> None:
    response = client.get("/wizard")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "root" in response.text


@needs_dist
def test_spa_fallback_keeps_api_routes() -> None:
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/nope").status_code == 404


@needs_dist
def test_missing_asset_is_not_html() -> None:
    response = client.get("/assets/does-not-exist.js")
    assert response.status_code == 404
    assert "text/html" not in response.headers.get("content-type", "")


# --- DCF wizard endpoints ---------------------------------------------------

from app.services import financials, market
from app.services.market import MarketInputs
from app.services.valuation import SUPPORTED_TICKERS, InvalidAssumptions


def test_dcf_recalc_passes_overrides(monkeypatch) -> None:
    captured = {}

    def fake_analyze(ticker, overrides=None, **_):
        captured["ticker"] = ticker
        captured["overrides"] = overrides
        return KO_RESULT

    monkeypatch.setattr(valuation, "analyze", fake_analyze)
    response = client.post("/api/dcf/ko", json={"projection_years": 7, "wacc": 0.09})

    assert response.status_code == 200
    assert captured["ticker"] == "ko"
    assert captured["overrides"].projection_years == 7
    assert captured["overrides"].wacc == 0.09


def test_dcf_recalc_rejects_out_of_range_body() -> None:
    response = client.post("/api/dcf/KO", json={"projection_years": 99})
    assert response.status_code == 422


def test_dcf_recalc_maps_invalid_assumptions(monkeypatch) -> None:
    def boom(ticker, overrides=None, **_):
        raise InvalidAssumptions("WACC must be greater than terminal growth")

    monkeypatch.setattr(valuation, "analyze", boom)
    response = client.post(
        "/api/dcf/KO", json={"wacc": 0.02, "terminal_growth_rate": 0.03}
    )

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_assumptions"


def test_sensitivity_endpoint_returns_grid(monkeypatch) -> None:
    monkeypatch.setattr(valuation, "analyze", lambda ticker, overrides=None, **_: KO_RESULT)
    response = client.post(
        "/api/dcf/KO/sensitivity", json={"wacc_steps": 3, "growth_steps": 3}
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["values"]) == 3
    assert all(len(row) == 3 for row in body["values"])
    assert body["base_wacc"] == KO_RESULT.assumptions.wacc
    assert body["base_terminal_growth"] == KO_RESULT.assumptions.terminal_growth_rate


def test_wacc_endpoint_returns_decomposition(monkeypatch) -> None:
    monkeypatch.setattr(
        financials, "load_company", lambda ticker: company_from_fixture("KO")
    )
    monkeypatch.setattr(
        market,
        "market_inputs",
        lambda ticker: MarketInputs(
            ticker="KO",
            price=60.0,
            beta_computed=0.55,
            beta_observations=104,
            beta_r_squared=0.35,
            risk_free_rate=0.042,
            as_of="2026-11-11",
            available=True,
        ),
    )
    response = client.get("/api/wacc/ko")

    assert response.status_code == 200
    body = response.json()
    assert 0 < body["wacc"] < 0.3
    assert body["cost_of_equity"] is not None
    assert body["inputs"]
    assert all(item["source"] for item in body["inputs"])


def test_wacc_endpoint_rejects_unsupported_ticker() -> None:
    response = client.get("/api/wacc/ZZZ")
    assert response.status_code == 422
    assert response.json()["error"] == "unsupported_ticker"


def test_ticker_search_returns_match() -> None:
    response = client.get("/api/tickers", params={"q": "KO", "limit": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["ticker"] == "KO"
    assert body["results"][0]["pilot"] is True


def test_ticker_search_defaults_to_pilots() -> None:
    response = client.get("/api/tickers")
    assert response.status_code == 200
    body = response.json()
    assert {row["ticker"] for row in body["results"]} == set(SUPPORTED_TICKERS)


def test_ticker_search_finds_non_pilot() -> None:
    response = client.get("/api/tickers", params={"q": "johnson", "limit": 5})
    assert response.status_code == 200
    rows = response.json()["results"]
    assert any(row["ticker"] == "JNJ" and row["pilot"] is False for row in rows)
