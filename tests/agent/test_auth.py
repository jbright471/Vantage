from fastapi.testclient import TestClient

from agent.app.auth import clear_replay_cache, sign_request_message, signature_message
from agent.app.main import app


TEST_AGENT_TOKEN = "agent-test-token-0000000000000000000000"


def test_agent_fails_closed_when_shared_token_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("VANTAGE_AGENT_SHARED_TOKEN", raising=False)

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["detail"] == "Agent authentication is not configured"


def test_agent_requires_bearer_token_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("VANTAGE_AGENT_SHARED_TOKEN", TEST_AGENT_TOKEN)
    monkeypatch.setenv("VANTAGE_AGENT_AUTH_MODE", "bearer")

    client = TestClient(app)

    assert client.get("/health").status_code == 401
    assert client.get("/health", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_agent_accepts_configured_bearer_token(monkeypatch) -> None:
    monkeypatch.setenv("VANTAGE_AGENT_SHARED_TOKEN", TEST_AGENT_TOKEN)
    monkeypatch.setenv("VANTAGE_AGENT_AUTH_MODE", "bearer")

    client = TestClient(app)
    response = client.get("/health", headers={"Authorization": f"Bearer {TEST_AGENT_TOKEN}"})

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_agent_accepts_hmac_signed_request(monkeypatch) -> None:
    clear_replay_cache()
    monkeypatch.setenv("VANTAGE_AGENT_SHARED_TOKEN", TEST_AGENT_TOKEN)
    monkeypatch.setenv("VANTAGE_AGENT_AUTH_MODE", "hmac")
    monkeypatch.setenv("VANTAGE_AGENT_KEY_ID", "agent-key-1")
    monkeypatch.setenv("VANTAGE_AGENT_AUTH_ALLOWED_SKEW_SECONDS", "99999999")
    timestamp = "1770000000"
    nonce = "nonce-1"
    message = signature_message("GET", "/health", timestamp, nonce, b"")
    signature = sign_request_message(TEST_AGENT_TOKEN, message)

    client = TestClient(app)
    response = client.get(
        "/health",
        headers={
            "X-Vantage-Timestamp": timestamp,
            "X-Vantage-Nonce": nonce,
            "X-Vantage-Signature": signature,
            "X-Vantage-Key-Id": "agent-key-1",
        },
    )

    assert response.status_code == 200


def test_agent_rejects_replayed_hmac_nonce(monkeypatch) -> None:
    clear_replay_cache()
    monkeypatch.setenv("VANTAGE_AGENT_SHARED_TOKEN", TEST_AGENT_TOKEN)
    monkeypatch.setenv("VANTAGE_AGENT_AUTH_MODE", "hmac")
    monkeypatch.setenv("VANTAGE_AGENT_AUTH_ALLOWED_SKEW_SECONDS", "99999999")
    timestamp = "1770000000"
    nonce = "nonce-replay"
    message = signature_message("GET", "/health", timestamp, nonce, b"")
    signature = sign_request_message(TEST_AGENT_TOKEN, message)
    headers = {
        "X-Vantage-Timestamp": timestamp,
        "X-Vantage-Nonce": nonce,
        "X-Vantage-Signature": signature,
    }

    client = TestClient(app)
    assert client.get("/health", headers=headers).status_code == 200
    assert client.get("/health", headers=headers).status_code == 401


def test_agent_action_allowlist_rejects_disallowed_action(monkeypatch) -> None:
    monkeypatch.setenv("VANTAGE_AGENT_ALLOWED_ACTIONS", "read")
    monkeypatch.setenv("VANTAGE_AGENT_SHARED_TOKEN", TEST_AGENT_TOKEN)
    monkeypatch.setenv("VANTAGE_AGENT_AUTH_MODE", "bearer")

    client = TestClient(app)
    response = client.post(
        "/capability-check",
        json={"model_name": "qwen3:latest"},
        headers={"Authorization": f"Bearer {TEST_AGENT_TOKEN}"},
    )

    assert response.status_code == 403


def test_agent_fails_closed_when_shared_token_is_weak(monkeypatch) -> None:
    monkeypatch.setenv("VANTAGE_AGENT_SHARED_TOKEN", "too-short")

    client = TestClient(app)
    response = client.get("/health", headers={"Authorization": "Bearer too-short"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Agent authentication is not configured"
