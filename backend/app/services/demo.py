from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import (
    EvalCase,
    EvalSchedule,
    EvalSuite,
    ModelPlacement,
    Node,
    NodeSnapshot,
    RoutingRule,
    RoutingRuleNode,
    Run,
    WarningRecord,
)


def demo_mode_enabled() -> bool:
    import os

    return os.getenv("VANTAGE_DEMO_MODE", "").strip().lower() in {"1", "true", "yes", "on"}


def seed_demo_data(session: Session) -> None:
    now = datetime.now(UTC)
    _seed_demo_nodes(session, now)
    _seed_demo_models(session, now)
    _seed_demo_routing(session)
    _seed_demo_runs(session, now)
    _seed_demo_eval_suite(session, now)
    _seed_demo_warning(session, now)
    session.commit()


def _seed_demo_nodes(session: Session, now: datetime) -> None:
    demo_nodes = [
        {
            "node_id": "demo-control",
            "display_name": "Demo Control",
            "base_url": "http://127.0.0.1:8000",
            "role": "primary",
            "health_status": "healthy",
            "captured_at": now,
            "gpu_json": [{"name": "NVIDIA RTX 5090", "memory_total_mb": 32768, "temperature_c": 54}],
            "cpu_json": {"usage_percent": 18},
            "memory_json": {"used_mb": 18432},
            "ollama_json": {
                "status": "ok",
                "models": [
                    {"name": "llama3.1:8b", "digest": "sha256:demo111"},
                    {"name": "qwen2.5-coder:14b", "digest": "sha256:demo222"},
                ],
                "errors": [],
            },
        },
        {
            "node_id": "demo-worker",
            "display_name": "Demo Worker",
            "base_url": "http://10.0.0.20:9110",
            "role": "remote",
            "health_status": "degraded",
            "captured_at": now - timedelta(seconds=8),
            "gpu_json": [{"name": "NVIDIA RTX 3090", "memory_total_mb": 24576, "temperature_c": 62}],
            "cpu_json": {"usage_percent": 41},
            "memory_json": {"used_mb": 28672},
            "ollama_json": {
                "status": "partial",
                "models": [{"name": "llama3.1:8b", "digest": "sha256:demo111"}],
                "errors": [{"source": "gpu", "error": "Transient telemetry timeout"}],
            },
        },
    ]

    for demo_node in demo_nodes:
        node = session.get(Node, demo_node["node_id"])
        if node is None:
            node = Node(
                node_id=demo_node["node_id"],
                display_name=demo_node["display_name"],
                base_url=demo_node["base_url"],
                role=demo_node["role"],
                enabled=True,
                created_from="demo",
            )
            session.add(node)
        node.last_seen_at = demo_node["captured_at"]
        snapshot = session.scalar(
            select(NodeSnapshot)
            .where(NodeSnapshot.node_id == demo_node["node_id"])
            .order_by(NodeSnapshot.captured_at.desc())
            .limit(1)
        )
        if snapshot is None:
            snapshot = NodeSnapshot(node_id=demo_node["node_id"], captured_at=demo_node["captured_at"])
            session.add(snapshot)
        snapshot.captured_at = demo_node["captured_at"]
        snapshot.gpu_json = demo_node["gpu_json"]
        snapshot.cpu_json = demo_node["cpu_json"]
        snapshot.memory_json = demo_node["memory_json"]
        snapshot.ollama_json = demo_node["ollama_json"]
        snapshot.health_status = demo_node["health_status"]


def _seed_demo_models(session: Session, now: datetime) -> None:
    placements = [
        ("demo-control", "llama3.1:8b", "sha256:demo111"),
        ("demo-worker", "llama3.1:8b", "sha256:demo111"),
        ("demo-control", "qwen2.5-coder:14b", "sha256:demo222"),
    ]
    for node_id, model_name, model_digest in placements:
        exists = session.scalar(
            select(ModelPlacement).where(
                ModelPlacement.node_id == node_id,
                ModelPlacement.model_name == model_name,
                ModelPlacement.model_digest == model_digest,
            )
        )
        if exists is not None:
            continue
        session.add(
            ModelPlacement(
                node_id=node_id,
                model_name=model_name,
                model_digest=model_digest,
                available=True,
                last_seen_at=now,
            )
        )


def _seed_demo_routing(session: Session) -> None:
    rules = [
        {
            "rule_id": "demo-interactive-local-first",
            "priority_class": "interactive",
            "model_name": "llama3.1:8b",
            "allow_degraded": False,
            "allow_stale": False,
            "minimum_eval_pass_rate": 0.9,
            "nodes": ["demo-control", "demo-worker"],
        },
        {
            "rule_id": "demo-batch-worker-first",
            "priority_class": "batch",
            "model_name": "llama3.1:8b",
            "allow_degraded": True,
            "allow_stale": False,
            "minimum_eval_pass_rate": 0.75,
            "nodes": ["demo-worker", "demo-control"],
        },
    ]

    for rule_data in rules:
        rule = session.get(RoutingRule, rule_data["rule_id"])
        if rule is None:
            rule = RoutingRule(rule_id=rule_data["rule_id"])
            session.add(rule)
        rule.priority_class = rule_data["priority_class"]
        rule.model_name = rule_data["model_name"]
        rule.enabled = True
        rule.allow_degraded = rule_data["allow_degraded"]
        rule.allow_stale = rule_data["allow_stale"]
        rule.allow_unreachable = False
        rule.minimum_eval_pass_rate = rule_data["minimum_eval_pass_rate"]

        existing_nodes = session.scalars(
            select(RoutingRuleNode).where(RoutingRuleNode.rule_id == rule_data["rule_id"])
        ).all()
        if existing_nodes:
            for rule_node in existing_nodes:
                session.delete(rule_node)
            session.flush()
        for index, node_id in enumerate(rule_data["nodes"]):
            session.add(RoutingRuleNode(rule_id=rule_data["rule_id"], node_id=node_id, sort_order=index))


def _seed_demo_runs(session: Session, now: datetime) -> None:
    runs = [
        Run(
            run_id="demo-run-capability-ok",
            source_type="inference",
            detail_type="capability_check",
            source_id="demo:capability:llama3.1",
            node_id="demo-control",
            model_name="llama3.1:8b",
            action_type="infer",
            status="success",
            started_at=now - timedelta(minutes=12),
            ended_at=now - timedelta(minutes=12) + timedelta(seconds=2),
            duration_ms=1840,
            summary="Demo capability check passed on demo-control",
            metadata_json={"response_preview": '{"mode":"ok","json":"yes"}', "demo": True},
        ),
        Run(
            run_id="demo-run-routing-dry-run",
            source_type="agent_action",
            detail_type="agent_action",
            source_id="demo:routing:interactive",
            node_id="demo-worker",
            model_name=None,
            action_type="routing_update",
            status="submitted_unverified",
            started_at=now - timedelta(minutes=7),
            ended_at=None,
            duration_ms=None,
            summary="Demo routing override submitted for remote worker",
            metadata_json={"target_node": "demo-worker", "demo": True},
        ),
        Run(
            run_id="demo-run-eval-failed",
            source_type="eval",
            detail_type="eval_attempt",
            source_id="demo:eval:json-contract",
            node_id="demo-worker",
            model_name="llama3.1:8b",
            action_type="eval",
            status="failed",
            started_at=now - timedelta(minutes=3),
            ended_at=now - timedelta(minutes=2, seconds=58),
            duration_ms=2120,
            summary="Demo eval failed expected JSON contract",
            metadata_json={
                "suite_id": "demo-suite-json-contracts",
                "suite_name": "Demo JSON Contracts",
                "case_id": "demo-case-answer-shape",
                "case_name": "Answer shape",
                "score": {
                    "passed": False,
                    "score": 0.0,
                    "reason": "expected_subset_mismatch",
                    "missing_or_mismatched": ["answer"],
                },
                "demo": True,
            },
        ),
    ]
    for run in runs:
        if session.get(Run, run.run_id) is None:
            session.add(run)


def _seed_demo_eval_suite(session: Session, now: datetime) -> None:
    if session.get(EvalSuite, "demo-suite-json-contracts") is None:
        session.add(
            EvalSuite(
                suite_id="demo-suite-json-contracts",
                name="Demo JSON Contracts",
                description="Sample prompt pack for checking structured local model responses.",
                created_at=now,
                metadata_json={"demo": True},
            )
        )
    if session.get(EvalCase, "demo-case-answer-shape") is None:
        session.add(
            EvalCase(
                case_id="demo-case-answer-shape",
                suite_id="demo-suite-json-contracts",
                name="Answer shape",
                prompt="Return JSON with an answer field set to 42.",
                expected_json={"answer": 42},
                score_type="json_subset",
                score_config_json={},
                sort_order=1,
            )
        )
    if session.get(EvalSchedule, "demo-schedule-json-contracts") is None:
        session.add(
            EvalSchedule(
                schedule_id="demo-schedule-json-contracts",
                suite_id="demo-suite-json-contracts",
                model_name="llama3.1:8b",
                node_id="demo-worker",
                interval_minutes=60,
                enabled=True,
                auto_execute=False,
                created_at=now,
                updated_at=now,
                next_run_at=now + timedelta(hours=1),
                metadata_json={"demo": True},
            )
        )


def _seed_demo_warning(session: Session, now: datetime) -> None:
    if session.get(WarningRecord, "demo-warning-worker-degraded") is not None:
        return
    session.add(
        WarningRecord(
            warning_id="demo-warning-worker-degraded",
            warning_type="demo_degraded_node",
            severity="warning",
            node_id="demo-worker",
            first_seen_at=now - timedelta(minutes=5),
            last_seen_at=now,
            status="active",
            summary="Demo worker is degraded so operators can see warning handling.",
            metadata_json={"demo": True},
        )
    )
