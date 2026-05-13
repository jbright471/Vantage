from datetime import UTC, datetime

from backend.app.services.polling import classify_health, extract_model_placements, normalize_snapshot


def test_classify_health_marks_partial_failure_as_degraded() -> None:
    snapshot = {
        "node_id": "remote-worker",
        "captured_at": datetime.now(UTC),
        "gpu_json": [],
        "cpu_json": {"usage_percent": 12},
        "memory_json": {"used_mb": 2048},
        "ollama_json": {"status": "error", "models": []},
    }

    normalized = normalize_snapshot(snapshot)

    assert classify_health(normalized) == "degraded"


def test_extract_model_placements_creates_rows_per_model() -> None:
    placements = extract_model_placements(
        node_id="remote-worker",
        ollama_payload={"models": [{"name": "qwen3.6:latest", "digest": "sha256:abc"}]},
    )

    assert placements[0]["node_id"] == "remote-worker"
    assert placements[0]["model_name"] == "qwen3.6:latest"
