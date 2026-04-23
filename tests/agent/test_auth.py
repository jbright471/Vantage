from fastapi.testclient import TestClient

from agent.app.main import app


def test_agent_requires_bearer_token_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("VANTAGE_AGENT_SHARED_TOKEN", "secret-token")

    client = TestClient(app)

    assert client.get("/health").status_code == 401
    assert client.get("/health", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_agent_accepts_configured_bearer_token(monkeypatch) -> None:
    monkeypatch.setenv("VANTAGE_AGENT_SHARED_TOKEN", "secret-token")

    client = TestClient(app)
    response = client.get("/health", headers={"Authorization": "Bearer secret-token"})

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
