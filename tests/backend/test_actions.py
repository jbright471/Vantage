from fastapi.testclient import TestClient
from datetime import UTC, datetime

from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import AppSetting, Node, NodeSnapshot, RoutingRuleNode, Run
from backend.app.services.actions import build_action_run_payload, build_idempotency_key


def _set_node_enabled_state(enabled_by_node: dict[str, bool]) -> None:
    with SessionLocal() as session:
        for node_id, enabled in enabled_by_node.items():
            node = session.get(Node, node_id)
            if node is not None:
                node.enabled = enabled
        session.commit()


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


def test_set_node_enabled_action_quarantines_node_and_records_run() -> None:
    with TestClient(app) as client:
        _set_node_enabled_state({"jedi": True, "bastet": True})
        response = client.patch("/api/actions/nodes/bastet/enabled", json={"enabled": False})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["node_id"] == "bastet"
    assert payload["metadata_json"]["previous_enabled"] is True
    assert payload["metadata_json"]["requested_enabled"] is False
    assert "batch-default" in payload["metadata_json"]["removed_from_routing_rules"]

    with SessionLocal() as session:
        node = session.get(Node, "bastet")
        setting = session.get(AppSetting, "node_enabled_overrides")
        route_nodes = session.query(RoutingRuleNode).filter(RoutingRuleNode.node_id == "bastet").all()
        run = session.get(Run, payload["run_id"])

    assert node is not None
    assert node.enabled is False
    assert setting is not None
    assert setting.value_json["nodes"]["bastet"] is False
    assert route_nodes == []
    assert run is not None
    assert run.action_type == "set-node-enabled"


def test_set_node_enabled_action_reenables_node_and_records_run() -> None:
    with TestClient(app) as client:
        _set_node_enabled_state({"jedi": True, "bastet": False})
        response = client.patch("/api/actions/nodes/bastet/enabled", json={"enabled": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["metadata_json"]["previous_enabled"] is False
    assert payload["metadata_json"]["requested_enabled"] is True

    with SessionLocal() as session:
        node = session.get(Node, "bastet")
        setting = session.get(AppSetting, "node_enabled_overrides")

    assert node is not None
    assert node.enabled is True
    assert setting is not None
    assert setting.value_json["nodes"]["bastet"] is True


def test_set_node_enabled_action_rejects_disabling_last_enabled_node() -> None:
    try:
        with TestClient(app) as client:
            _set_node_enabled_state({"jedi": True, "bastet": False})
            response = client.patch("/api/actions/nodes/jedi/enabled", json={"enabled": False})

        assert response.status_code == 400
        assert "last enabled node" in response.json()["detail"].lower()

        with SessionLocal() as session:
            node = session.get(Node, "jedi")

        assert node is not None
        assert node.enabled is True
    finally:
        _set_node_enabled_state({"jedi": True, "bastet": True})


def test_set_local_ollama_endpoint_action_disables_endpoint_and_records_run() -> None:
    with TestClient(app) as client:
        response = client.patch(
            "/api/actions/nodes/jedi/local-ollama-endpoint",
            json={"endpoint_url": "http://127.0.0.1:11435", "disabled": True},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["node_id"] == "jedi"
    assert payload["metadata_json"]["endpoint_url"] == "http://127.0.0.1:11435"
    assert payload["metadata_json"]["requested_disabled"] is True
    assert payload["metadata_json"]["disabled_endpoints"] == ["http://127.0.0.1:11435"]

    with SessionLocal() as session:
        setting = session.get(AppSetting, "local_ollama_endpoint_overrides")
        run = session.get(Run, payload["run_id"])

    assert setting is not None
    assert setting.value_json["disabled"] == ["http://127.0.0.1:11435"]
    assert run is not None
    assert run.action_type == "set-local-ollama-endpoint-disabled"


def test_set_local_ollama_endpoint_action_rejects_remote_nodes() -> None:
    with TestClient(app) as client:
        response = client.patch(
            "/api/actions/nodes/bastet/local-ollama-endpoint",
            json={"endpoint_url": "http://127.0.0.1:11435", "disabled": True},
        )

    assert response.status_code == 400
    assert "remote agent" in response.json()["detail"].lower()


def test_set_local_ollama_endpoint_action_rejects_last_enabled_endpoint() -> None:
    with TestClient(app) as client:
        response = client.patch(
            "/api/actions/nodes/jedi/local-ollama-endpoint",
            json={"endpoint_url": "http://127.0.0.1:11434", "disabled": True},
        )

    assert response.status_code == 400
    assert "last enabled local ollama endpoint" in response.json()["detail"].lower()
