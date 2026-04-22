from fastapi.testclient import TestClient

from agent.app.main import app


def test_agent_exposes_health_gpu_and_models(monkeypatch) -> None:
    monkeypatch.setattr("agent.app.collectors.get_health", lambda: {"status": "ok", "node_id": "bastet"})
    monkeypatch.setattr(
        "agent.app.collectors.get_gpu_stats",
        lambda: [{"name": "RTX 3090", "memory_total_mb": 24576, "temperature_c": 42}],
    )
    monkeypatch.setattr(
        "agent.app.collectors.get_models",
        lambda: [{"model_name": "qwen3.6:latest", "model_digest": "sha256:abc", "available": True}],
    )

    client = TestClient(app)

    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/gpu").json()["gpus"][0]["name"] == "RTX 3090"
    assert client.get("/models").json()["models"][0]["model_name"] == "qwen3.6:latest"
