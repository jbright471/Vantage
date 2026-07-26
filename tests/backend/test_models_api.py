from fastapi.testclient import TestClient

from backend.app.main import app


def test_local_capability_check_endpoint_returns_success(monkeypatch) -> None:
    called_urls: list[str] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"response": '{"mode":"inference","json":true,"notes":"ok"}'}

    def fake_post(url, *args, **kwargs):
        called_urls.append(url)
        return FakeResponse()

    monkeypatch.setenv("VANTAGE_LOCAL_OLLAMA_BASE_URLS", "http://host.docker.internal:11400")
    monkeypatch.setattr("backend.app.api.models.httpx.post", fake_post)

    with TestClient(app) as client:
        response = client.post(
            "/api/models/capability-check",
            json={"model_name": "qwen3.6:latest", "node_id": "control-plane"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["detail_type"] == "capability_check"
    assert response.json()["metadata_json"]["response_json"] == {
        "mode": "inference",
        "json": True,
        "notes": "ok",
    }
    assert called_urls == ["http://host.docker.internal:11400/api/generate"]


def test_local_capability_check_rejects_non_deterministic_response(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"response": '{"mode":"offline","json":true,"notes":"invented"}'}

    monkeypatch.setattr("backend.app.api.models.httpx.post", lambda *args, **kwargs: FakeResponse())

    with TestClient(app) as client:
        response = client.post(
            "/api/models/capability-check",
            json={"model_name": "qwen3.6:latest", "node_id": "control-plane"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert "deterministic handshake" in response.json()["metadata_json"]["errors"][0]["error"]


def test_remote_capability_check_failure_returns_failed_run(monkeypatch) -> None:
    class OfflineAgentClient:
        def post_json(self, *args, **kwargs):
            raise RuntimeError("agent offline")

    monkeypatch.setattr(
        "backend.app.api.models.build_remote_agent_client",
        lambda *args, **kwargs: OfflineAgentClient(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/models/capability-check",
            json={"model_name": "qwen3.6-hermes:latest", "node_id": "remote-worker"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
