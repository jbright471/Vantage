from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import ModelPlacement, Node, NodeSnapshot, Run


def test_update_routing_rule_endpoint_reorders_nodes() -> None:
    with TestClient(app) as client:
        response = client.put(
            "/api/routing/interactive-default",
            json={"preferred_nodes": ["remote-worker", "control-plane"]},
        )

    assert response.status_code == 200
    assert response.json()["preferred_nodes"] == ["remote-worker", "control-plane"]


def test_dry_run_routing_explains_skipped_degraded_node() -> None:
    with TestClient(app) as client:
        now = datetime.now(UTC)
        with SessionLocal() as session:
            for node_id in ("control-plane", "remote-worker"):
                node = session.get(Node, node_id)
                assert node is not None
                node.last_seen_at = now
            session.add_all(
                [
                    NodeSnapshot(
                        node_id="remote-worker",
                        captured_at=now,
                        gpu_json=[],
                        cpu_json={},
                        memory_json={},
                        ollama_json={"status": "error", "models": []},
                        health_status="degraded",
                    ),
                    NodeSnapshot(
                        node_id="control-plane",
                        captured_at=now,
                        gpu_json=[],
                        cpu_json={},
                        memory_json={},
                        ollama_json={"status": "ok", "models": []},
                        health_status="healthy",
                    ),
                ]
            )
            session.commit()

        response = client.post(
            "/api/routing/scheduled-default/dry-run",
            json={"preferred_nodes": ["remote-worker", "control-plane"]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_order"] == ["remote-worker", "control-plane"]
    assert payload["selected_node"] == "control-plane"
    assert payload["decisions"][0]["node_id"] == "remote-worker"
    assert payload["decisions"][0]["decision"] == "rejected"
    assert "health:degraded" in payload["decisions"][0]["reasons"]
    assert payload["decisions"][1]["decision"] == "selected"
    assert "Preferred node 'remote-worker' would be skipped" in payload["warnings"][0]


def test_routing_rule_lifecycle_records_history() -> None:
    rule_id = f"model-specific-{uuid4().hex[:8]}"

    with TestClient(app) as client:
        create_response = client.post(
            "/api/routing",
            json={
                "rule_id": rule_id,
                "priority_class": "interactive",
                "model_name": "qwen3.5:27b",
                "preferred_nodes": ["control-plane", "remote-worker"],
                "minimum_eval_pass_rate": 0.75,
            },
        )
        update_response = client.patch(
            f"/api/routing/{rule_id}",
            json={
                "enabled": False,
                "allow_degraded": True,
                "allow_stale": True,
                "minimum_eval_pass_rate": 0.5,
            },
        )
        delete_response = client.delete(f"/api/routing/{rule_id}")
        history_response = client.get(f"/api/routing/{rule_id}/history")

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["rule_id"] == rule_id
    assert created["model_name"] == "qwen3.5:27b"
    assert created["minimum_eval_pass_rate"] == 0.75

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["enabled"] is False
    assert updated["allow_degraded"] is True
    assert updated["allow_stale"] is True
    assert updated["minimum_eval_pass_rate"] == 0.5

    assert delete_response.status_code == 200
    history = history_response.json()
    assert [item["action_type"] for item in history[:3]] == ["delete", "update", "create"]


def test_dry_run_uses_model_placement_and_eval_pass_rate_constraints() -> None:
    rule_id = f"eval-aware-{uuid4().hex[:8]}"
    model_name = f"qwen-route-{uuid4().hex[:8]}"
    now = datetime.now(UTC)

    with TestClient(app) as client:
        client.post(
            "/api/routing",
            json={
                "rule_id": rule_id,
                "priority_class": "batch",
                "model_name": model_name,
                "preferred_nodes": ["remote-worker", "control-plane"],
                "minimum_eval_pass_rate": 0.75,
            },
        )

        with SessionLocal() as session:
            for node_id in ("control-plane", "remote-worker"):
                node = session.get(Node, node_id)
                assert node is not None
                node.last_seen_at = now
                session.add(
                    NodeSnapshot(
                        node_id=node_id,
                        captured_at=now,
                        gpu_json=[],
                        cpu_json={},
                        memory_json={},
                        ollama_json={"status": "ok", "models": [{"name": model_name}]},
                        health_status="healthy",
                    )
                )
                session.add(
                    ModelPlacement(
                        node_id=node_id,
                        model_name=model_name,
                        model_digest=f"sha256:{node_id}",
                        available=True,
                        last_seen_at=now,
                    )
                )

            session.add_all(
                [
                    Run(
                        run_id=f"eval-{uuid4().hex}",
                        source_type="eval",
                        detail_type="eval_attempt",
                        source_id="test",
                        node_id="remote-worker",
                        model_name=model_name,
                        action_type=None,
                        status="success",
                        idempotency_key=None,
                        started_at=now,
                        ended_at=now,
                        duration_ms=10,
                        summary="Eval pass",
                        metadata_json={"score": {"passed": True}, "suite_id": "route", "case_id": "pass"},
                    ),
                    Run(
                        run_id=f"eval-{uuid4().hex}",
                        source_type="eval",
                        detail_type="eval_attempt",
                        source_id="test",
                        node_id="remote-worker",
                        model_name=model_name,
                        action_type=None,
                        status="failed",
                        idempotency_key=None,
                        started_at=now,
                        ended_at=now,
                        duration_ms=10,
                        summary="Eval fail",
                        metadata_json={"score": {"passed": False}, "suite_id": "route", "case_id": "fail"},
                    ),
                    Run(
                        run_id=f"eval-{uuid4().hex}",
                        source_type="eval",
                        detail_type="eval_attempt",
                        source_id="test",
                        node_id="control-plane",
                        model_name=model_name,
                        action_type=None,
                        status="success",
                        idempotency_key=None,
                        started_at=now,
                        ended_at=now,
                        duration_ms=10,
                        summary="Eval pass",
                        metadata_json={"score": {"passed": True}, "suite_id": "route", "case_id": "pass"},
                    ),
                ]
            )
            session.commit()

        response = client.post(f"/api/routing/{rule_id}/dry-run", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_node"] == "control-plane"
    assert "eval_pass_rate_below_minimum:0.5000<0.7500" in payload["decisions"][0]["reasons"]
    assert payload["decisions"][0]["eval_pass_rate"] == 0.5
    assert payload["decisions"][1]["decision"] == "selected"
