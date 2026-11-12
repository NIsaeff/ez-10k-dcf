from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_chat_requires_messages() -> None:
    response = client.post("/api/chat", json={"messages": []})
    assert response.status_code == 422


def test_chat_rejects_unknown_role() -> None:
    response = client.post(
        "/api/chat",
        json={"messages": [{"role": "tool", "content": "nope"}]},
    )
    assert response.status_code == 422
