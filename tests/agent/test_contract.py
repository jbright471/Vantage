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


def test_agent_exposes_runs_and_capability_check(monkeypatch) -> None:
    monkeypatch.setattr(
        "agent.app.collectors.get_runs",
        lambda: [
            {
                "run_id": "run-1",
                "source_type": "remote_agent",
                "detail_type": "ollama_loaded_model",
                "source_id": "ollama-ps:http://127.0.0.1:11435/qwen",
                "node_id": "bastet",
                "model_name": "qwen3.6:latest",
                "action_type": "infer",
                "status": "running",
                "started_at": "2026-04-23T12:00:00+00:00",
                "ended_at": None,
                "duration_ms": None,
                "summary": "Model qwen3.6:latest is currently loaded on bastet",
                "metadata_json": {},
            }
        ],
    )
    monkeypatch.setattr(
        "agent.app.collectors.run_capability_check",
        lambda model_name, prompt=None: {
            "run_id": "run-2",
            "source_type": "inference",
            "detail_type": "capability_check",
            "source_id": f"capability-check:bastet:{model_name}",
            "node_id": "bastet",
            "model_name": model_name,
            "action_type": "infer",
            "status": "success",
            "started_at": "2026-04-23T12:05:00+00:00",
            "ended_at": "2026-04-23T12:05:01+00:00",
            "duration_ms": 1000,
            "summary": f"Capability check passed for {model_name} on bastet",
            "metadata_json": {"response_preview": "{}"},
        },
    )

    client = TestClient(app)

    assert client.get("/runs").json()["runs"][0]["run_id"] == "run-1"
    assert client.post("/capability-check", json={"model_name": "qwen3.6:latest"}).json()["status"] == "success"


def test_agent_exposes_eval_attempt(monkeypatch) -> None:
    monkeypatch.setattr(
        "agent.app.collectors.run_eval_attempt",
        lambda model_name, prompt, expected_json=None: {
            "run_id": "run-3",
            "source_type": "eval",
            "detail_type": "eval_attempt",
            "source_id": f"eval-attempt:bastet:{model_name}",
            "node_id": "bastet",
            "model_name": model_name,
            "action_type": "eval",
            "status": "success",
            "started_at": "2026-04-23T12:05:00+00:00",
            "ended_at": "2026-04-23T12:05:01+00:00",
            "duration_ms": 1000,
            "summary": f"Eval attempt passed for {model_name} on bastet",
            "metadata_json": {"response_text": "{}", "score": {"passed": True, "score": 1.0}},
        },
    )

    client = TestClient(app)

    response = client.post(
        "/eval-attempt",
        json={"model_name": "qwen3.6:latest", "prompt": "Return JSON", "expected_json": {}},
    )

    assert response.status_code == 200
    assert response.json()["detail_type"] == "eval_attempt"
