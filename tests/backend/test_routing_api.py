from datetime import UTC, datetime, timedelta
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
                        metadata_json={
                            "score": {"passed": True},
                            "suite_id": "route",
                            "case_id": "pass",
                            "model_digest": "sha256:remote-worker",
                        },
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
                        metadata_json={
                            "score": {"passed": False},
                            "suite_id": "route",
                            "case_id": "fail",
                            "model_digest": "sha256:remote-worker",
                        },
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
                        metadata_json={
                            "score": {"passed": True},
                            "suite_id": "route",
                            "case_id": "pass",
                            "model_digest": "sha256:control-plane",
                        },
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
    assert payload["decisions"][0]["eval_evidence_state"] == "failed"
    assert payload["decisions"][1]["decision"] == "selected"
    assert payload["decisions"][1]["eval_evidence_state"] == "validated"


def _seed_healthy_nodes(session, *, model_name: str, digests: dict[str, str], now: datetime) -> None:
    """Make every named node healthy, live, and carrying an available placement."""
    for node_id, digest in digests.items():
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
                model_digest=digest,
                available=True,
                last_seen_at=now,
            )
        )


def _eval_run(
    *,
    node_id: str,
    model_name: str,
    passed: bool,
    started_at: datetime,
    suite_id: str,
    model_digest: str | None,
) -> Run:
    metadata: dict = {
        "score": {"passed": passed},
        "suite_id": suite_id,
        "case_id": "pass" if passed else "fail",
    }
    if model_digest is not None:
        metadata["model_digest"] = model_digest
    return Run(
        run_id=f"eval-{uuid4().hex}",
        source_type="eval",
        detail_type="eval_attempt",
        source_id="test",
        node_id=node_id,
        model_name=model_name,
        action_type=None,
        status="success" if passed else "failed",
        idempotency_key=None,
        started_at=started_at,
        ended_at=started_at,
        duration_ms=10,
        summary="Eval attempt",
        metadata_json=metadata,
    )


def test_dry_run_rejects_nodes_without_any_eval_evidence() -> None:
    """A configured minimum with zero recorded evidence must not read as a pass."""
    rule_id = f"unverified-{uuid4().hex[:8]}"
    model_name = f"qwen-unverified-{uuid4().hex[:8]}"
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
            _seed_healthy_nodes(
                session,
                model_name=model_name,
                digests={"remote-worker": "sha256:worker", "control-plane": "sha256:control"},
                now=now,
            )
            session.commit()

        response = client.post(f"/api/routing/{rule_id}/dry-run", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_node"] is None
    for decision in payload["decisions"]:
        assert decision["decision"] == "rejected"
        assert decision["eval_evidence_state"] == "unverified"
        assert decision["eval_pass_rate"] is None
        assert decision["eval_evidence_sample_size"] == 0
        assert "eval_evidence:unverified" in decision["reasons"]
    assert any("No in-scope evaluation evidence" in warning for warning in payload["warnings"])


def test_dry_run_ignores_eval_evidence_recorded_for_another_suite() -> None:
    rule_id = f"suite-scope-{uuid4().hex[:8]}"
    model_name = f"qwen-suite-{uuid4().hex[:8]}"
    now = datetime.now(UTC)

    with TestClient(app) as client:
        client.post(
            "/api/routing",
            json={
                "rule_id": rule_id,
                "priority_class": "batch",
                "model_name": model_name,
                "preferred_nodes": ["remote-worker"],
                "minimum_eval_pass_rate": 0.75,
                "required_eval_suite_id": "contract-suite",
            },
        )
        with SessionLocal() as session:
            _seed_healthy_nodes(
                session,
                model_name=model_name,
                digests={"remote-worker": "sha256:worker"},
                now=now,
            )
            session.add_all(
                [
                    _eval_run(
                        node_id="remote-worker",
                        model_name=model_name,
                        passed=True,
                        started_at=now,
                        suite_id="smoke-suite",
                        model_digest="sha256:worker",
                    )
                    for _ in range(4)
                ]
            )
            session.commit()

        response = client.post(f"/api/routing/{rule_id}/dry-run", json={})

    assert response.status_code == 200
    payload = response.json()
    decision = payload["decisions"][0]
    assert payload["selected_node"] is None
    assert decision["eval_evidence_state"] == "unverified"
    assert decision["eval_evidence_suite_id"] == "contract-suite"
    assert "eval_evidence:unverified" in decision["reasons"]


def test_dry_run_ignores_eval_evidence_recorded_for_another_model_digest() -> None:
    rule_id = f"digest-scope-{uuid4().hex[:8]}"
    model_name = f"qwen-digest-{uuid4().hex[:8]}"
    now = datetime.now(UTC)

    with TestClient(app) as client:
        client.post(
            "/api/routing",
            json={
                "rule_id": rule_id,
                "priority_class": "batch",
                "model_name": model_name,
                "preferred_nodes": ["remote-worker"],
                "minimum_eval_pass_rate": 0.75,
                "required_eval_suite_id": "contract-suite",
            },
        )
        with SessionLocal() as session:
            _seed_healthy_nodes(
                session,
                model_name=model_name,
                digests={"remote-worker": "sha256:current-artifact"},
                now=now,
            )
            session.add_all(
                [
                    _eval_run(
                        node_id="remote-worker",
                        model_name=model_name,
                        passed=True,
                        started_at=now,
                        suite_id="contract-suite",
                        model_digest="sha256:superseded-artifact",
                    )
                    for _ in range(4)
                ]
            )
            session.commit()

        response = client.post(f"/api/routing/{rule_id}/dry-run", json={})

    assert response.status_code == 200
    payload = response.json()
    decision = payload["decisions"][0]
    assert payload["selected_node"] is None
    assert decision["eval_evidence_state"] == "unverified"
    assert decision["eval_evidence_model_digest"] == "sha256:current-artifact"
    assert "eval_evidence:unverified" in decision["reasons"]


def test_dry_run_reports_evidence_outside_the_recency_window_as_stale() -> None:
    rule_id = f"stale-evidence-{uuid4().hex[:8]}"
    model_name = f"qwen-stale-{uuid4().hex[:8]}"
    now = datetime.now(UTC)
    long_ago = now - timedelta(days=60)

    with TestClient(app) as client:
        client.post(
            "/api/routing",
            json={
                "rule_id": rule_id,
                "priority_class": "batch",
                "model_name": model_name,
                "preferred_nodes": ["remote-worker"],
                "minimum_eval_pass_rate": 0.75,
                "required_eval_suite_id": "contract-suite",
            },
        )
        with SessionLocal() as session:
            _seed_healthy_nodes(
                session,
                model_name=model_name,
                digests={"remote-worker": "sha256:worker"},
                now=now,
            )
            session.add_all(
                [
                    _eval_run(
                        node_id="remote-worker",
                        model_name=model_name,
                        passed=True,
                        started_at=long_ago,
                        suite_id="contract-suite",
                        model_digest="sha256:worker",
                    )
                    for _ in range(4)
                ]
            )
            session.commit()

        response = client.post(f"/api/routing/{rule_id}/dry-run", json={})

    assert response.status_code == 200
    payload = response.json()
    decision = payload["decisions"][0]
    assert payload["selected_node"] is None
    assert decision["eval_evidence_state"] == "stale"
    assert decision["eval_pass_rate"] == 1.0
    assert decision["eval_evidence_age_seconds"] > payload["policy"]["eval_evidence_max_age_seconds"]
    assert "eval_evidence:stale" in decision["reasons"]


def test_dry_run_selects_unverified_node_when_the_operator_opts_in() -> None:
    rule_id = f"opt-in-unverified-{uuid4().hex[:8]}"
    model_name = f"qwen-opt-in-{uuid4().hex[:8]}"
    now = datetime.now(UTC)

    with TestClient(app) as client:
        client.post(
            "/api/routing",
            json={
                "rule_id": rule_id,
                "priority_class": "batch",
                "model_name": model_name,
                "preferred_nodes": ["remote-worker"],
                "minimum_eval_pass_rate": 0.75,
                "allow_unverified": True,
            },
        )
        with SessionLocal() as session:
            _seed_healthy_nodes(
                session,
                model_name=model_name,
                digests={"remote-worker": "sha256:worker"},
                now=now,
            )
            session.commit()

        response = client.post(f"/api/routing/{rule_id}/dry-run", json={})

    assert response.status_code == 200
    payload = response.json()
    decision = payload["decisions"][0]
    assert payload["policy"]["allow_unverified"] is True
    assert payload["selected_node"] == "remote-worker"
    assert decision["decision"] == "selected"
    assert decision["eval_evidence_state"] == "unverified"
    assert "allowed_eval_evidence:unverified" in decision["reasons"]
    assert any("unverified nodes are accepted" in warning for warning in payload["warnings"])


def test_opting_into_stale_evidence_still_enforces_the_minimum_pass_rate() -> None:
    """Accepting expired evidence is not the same as accepting failing evidence."""
    rule_id = f"opt-in-stale-{uuid4().hex[:8]}"
    model_name = f"qwen-opt-stale-{uuid4().hex[:8]}"
    now = datetime.now(UTC)
    long_ago = now - timedelta(days=60)

    with TestClient(app) as client:
        client.post(
            "/api/routing",
            json={
                "rule_id": rule_id,
                "priority_class": "batch",
                "model_name": model_name,
                "preferred_nodes": ["remote-worker", "control-plane"],
                "minimum_eval_pass_rate": 0.75,
                "required_eval_suite_id": "contract-suite",
                "allow_stale_evidence": True,
            },
        )
        with SessionLocal() as session:
            _seed_healthy_nodes(
                session,
                model_name=model_name,
                digests={"remote-worker": "sha256:worker", "control-plane": "sha256:control"},
                now=now,
            )
            session.add_all(
                [
                    _eval_run(
                        node_id="remote-worker",
                        model_name=model_name,
                        passed=False,
                        started_at=long_ago,
                        suite_id="contract-suite",
                        model_digest="sha256:worker",
                    ),
                    _eval_run(
                        node_id="control-plane",
                        model_name=model_name,
                        passed=True,
                        started_at=long_ago,
                        suite_id="contract-suite",
                        model_digest="sha256:control",
                    ),
                ]
            )
            session.commit()

        response = client.post(f"/api/routing/{rule_id}/dry-run", json={})

    assert response.status_code == 200
    payload = response.json()
    rejected, selected = payload["decisions"]
    assert rejected["decision"] == "rejected"
    assert rejected["eval_evidence_state"] == "stale"
    assert "allowed_eval_evidence:stale" in rejected["reasons"]
    assert "eval_pass_rate_below_minimum:0.0000<0.7500" in rejected["reasons"]
    assert selected["decision"] == "selected"
    assert selected["eval_evidence_state"] == "stale"
    assert payload["selected_node"] == "control-plane"


def test_routing_rules_without_a_minimum_report_evidence_without_blocking() -> None:
    rule_id = f"no-minimum-{uuid4().hex[:8]}"
    model_name = f"qwen-no-min-{uuid4().hex[:8]}"
    now = datetime.now(UTC)

    with TestClient(app) as client:
        client.post(
            "/api/routing",
            json={
                "rule_id": rule_id,
                "priority_class": "batch",
                "model_name": model_name,
                "preferred_nodes": ["remote-worker"],
            },
        )
        with SessionLocal() as session:
            _seed_healthy_nodes(
                session,
                model_name=model_name,
                digests={"remote-worker": "sha256:worker"},
                now=now,
            )
            session.commit()

        response = client.post(f"/api/routing/{rule_id}/dry-run", json={})

    assert response.status_code == 200
    payload = response.json()
    decision = payload["decisions"][0]
    assert payload["selected_node"] == "remote-worker"
    assert decision["eval_evidence_state"] == "unverified"
    assert "eval_evidence_note:unverified_not_enforced" in decision["reasons"]
    assert payload["warnings"] == []
