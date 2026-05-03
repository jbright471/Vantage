from fastapi.testclient import TestClient
from datetime import UTC, datetime

from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import NodeSnapshot, Run
from backend.app.services.actions import build_action_run_payload, build_idempotency_key


def test_build_idempotency_key_is_stable_for_same_request() -> None:
    left = build_idempotency_key(
        action_type="restart-agent",
        target_node_id="bastet",
        target_resource_id="agent",
        payload={"service": "vantage-agent"},
        dedupe_window=30,
    )
    right = build_idempotency_key(
        action_type="restart-agent",
        target_node_id="bastet",
        target_resource_id="agent",
        payload={"service": "vantage-agent"},
        dedupe_window=30,
    )

    assert left == right


def test_build_action_run_payload_uses_submitted_unverified() -> None:
    payload = build_action_run_payload(node_id="bastet", summary="Refresh node bastet")

    assert payload["status"] == "submitted_unverified"
    assert payload["node_id"] == "bastet"


def test_refresh_node_action_endpoint_verifies_success(monkeypatch) -> None:
    async def fake_collect(node, runtime_config):
        return {
            "node_id": node.node_id,
            "captured_at": datetime(2026, 5, 3, 12, 0, tzinfo=UTC),
            "gpu_json": [],
            "cpu_json": {"usage_percent": 9},
            "memory_json": {"used_mb": 2048},
            "ollama_json": {"status": "ok", "models": [], "errors": []},
        }

    monkeypatch.setattr("backend.app.services.runtime.collect_snapshot_for_node", fake_collect)

    with TestClient(app) as client:
        response = client.post("/api/actions/refresh-node/bastet")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["node_id"] == "bastet"
    assert payload["metadata_json"]["verified"] is True
    assert payload["metadata_json"]["observed_status"] == "healthy"

    with SessionLocal() as session:
        run = session.get(Run, payload["run_id"])
        snapshot = session.query(NodeSnapshot).filter(NodeSnapshot.node_id == "bastet").order_by(
            NodeSnapshot.snapshot_id.desc()
        ).first()

    assert run is not None
    assert run.status == "success"
    assert snapshot is not None


def test_refresh_node_action_endpoint_records_failed_verification(monkeypatch) -> None:
    async def fake_collect(node, runtime_config):
        raise RuntimeError("collector unavailable")

    monkeypatch.setattr("backend.app.services.runtime.collect_snapshot_for_node", fake_collect)

    with TestClient(app) as client:
        response = client.post("/api/actions/refresh-node/jedi")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["node_id"] == "jedi"
    assert payload["metadata_json"]["verified"] is False
    assert payload["metadata_json"]["errors"][0]["error"] == "collector unavailable"
