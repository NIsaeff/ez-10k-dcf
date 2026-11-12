from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_echoes_last_user_message() -> None:
    response = client.post(
        "/api/chat",
        json={
            "messages": [
                {"role": "assistant", "content": "Ask me about a 10-K."},
                {"role": "user", "content": "value KO"},
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Echo: value KO"
    assert body["valuation"] is None


def test_chat_requires_messages() -> None:
    response = client.post("/api/chat", json={"messages": []})
    assert response.status_code == 422


def test_chat_rejects_unknown_role() -> None:
    response = client.post(
        "/api/chat",
        json={"messages": [{"role": "tool", "content": "nope"}]},
    )
    assert response.status_code == 422
