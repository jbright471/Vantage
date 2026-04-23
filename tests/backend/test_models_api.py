from fastapi.testclient import TestClient

from backend.app.main import app


def test_local_capability_check_endpoint_returns_success(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"response": '{"mode":"ok","json":"yes","notes":"healthy"}'}

    monkeypatch.setattr("backend.app.api.models.httpx.post", lambda *args, **kwargs: FakeResponse())

    with TestClient(app) as client:
        response = client.post(
            "/api/models/capability-check",
            json={"model_name": "qwen3.6:latest", "node_id": "jedi"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["detail_type"] == "capability_check"


def test_remote_capability_check_failure_returns_failed_run(monkeypatch) -> None:
    def fake_post(*args, **kwargs):
        raise RuntimeError("agent offline")

    monkeypatch.setattr("backend.app.api.models.httpx.post", fake_post)

    with TestClient(app) as client:
        response = client.post(
            "/api/models/capability-check",
            json={"model_name": "qwen3.6-hermes:latest", "node_id": "bastet"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
