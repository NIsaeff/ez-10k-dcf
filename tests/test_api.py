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
    monkeypatch.setattr(valuation, "analyze", lambda ticker: KO_RESULT)
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
    def boom(ticker: str) -> None:
        raise InsufficientData(ticker, ["shares_outstanding"])

    monkeypatch.setattr(valuation, "analyze", boom)
    response = client.post("/api/analyze/KO")
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "insufficient_data"
    assert body["missing_fields"] == ["shares_outstanding"]


def test_chat_values_a_ticker(monkeypatch) -> None:
    monkeypatch.setattr(valuation, "analyze", lambda ticker: KO_RESULT)
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
    def boom(ticker: str) -> None:
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
