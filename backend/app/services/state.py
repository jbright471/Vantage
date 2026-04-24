from datetime import UTC, datetime

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import BootstrapConfig, DEFAULT_BOOTSTRAP_CONFIG_PATH, load_bootstrap_config
from backend.app.models import ModelPlacement, Node, NodeSnapshot, RoutingRule, RoutingRuleNode, Run, WarningRecord
from backend.app.services.runs import serialize_run


def _timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def get_nodes_state(session: Session, config: BootstrapConfig | None = None) -> list[dict]:
    active_config = config or load_bootstrap_config(DEFAULT_BOOTSTRAP_CONFIG_PATH)
    nodes = session.scalars(select(Node).order_by(Node.display_name)).all()
    snapshots = session.scalars(select(NodeSnapshot).order_by(NodeSnapshot.captured_at.desc())).all()
    latest_snapshot_by_node: dict[str, NodeSnapshot] = {}
    for snapshot in snapshots:
        latest_snapshot_by_node.setdefault(snapshot.node_id, snapshot)

    state: list[dict] = []
    now = datetime.now(UTC)
    for node in nodes:
        latest_snapshot = latest_snapshot_by_node.get(node.node_id)
        last_seen_at = _timestamp(node.last_seen_at)
        freshness = "stale"
        observed_status = "unreachable"

        if last_seen_at is not None:
            age_seconds = (now - last_seen_at).total_seconds()
            freshness = "stale" if age_seconds >= active_config.stale_after_seconds else "live"
            if age_seconds < active_config.unreachable_after_seconds and latest_snapshot is not None:
                observed_status = latest_snapshot.health_status

        state.append(
            {
                "node_id": node.node_id,
                "display_name": node.display_name,
                "base_url": node.base_url,
                "role": node.role,
                "enabled": node.enabled,
                "created_from": node.created_from,
                "observed_status": observed_status,
                "freshness": freshness,
                "last_seen_at": last_seen_at.isoformat() if last_seen_at else None,
                "gpu_stats": latest_snapshot.gpu_json if latest_snapshot is not None else [],
                "cpu_usage_percent": latest_snapshot.cpu_json.get("usage_percent")
                if latest_snapshot is not None
                else None,
                "memory_used_mb": latest_snapshot.memory_json.get("used_mb")
                if latest_snapshot is not None
                else None,
                "ollama_status": latest_snapshot.ollama_json.get("status")
                if latest_snapshot is not None
                else None,
                "ollama_errors": latest_snapshot.ollama_json.get("errors", [])
                if latest_snapshot is not None
                else [],
                "model_count": len(latest_snapshot.ollama_json.get("models", []))
                if latest_snapshot is not None
                else 0,
            }
        )
    return state


def get_runs_state(session: Session) -> list[dict]:
    runs = session.scalars(select(Run).order_by(Run.started_at.desc())).all()
    return [serialize_run(run) for run in runs]


def get_models_state(session: Session) -> list[dict]:
    placements = session.scalars(select(ModelPlacement).order_by(ModelPlacement.model_name, ModelPlacement.node_id)).all()
    grouped: dict[str, list[str]] = defaultdict(list)
    placement_details: dict[str, list[dict]] = defaultdict(list)
    for placement in placements:
        grouped[placement.model_name].append(placement.node_id)
        placement_details[placement.model_name].append(
            {
                "node_id": placement.node_id,
                "model_digest": placement.model_digest,
                "available": placement.available,
            }
        )
    return [
        {
            "model_name": model_name,
            "placements": nodes,
            "placement_details": placement_details[model_name],
        }
        for model_name, nodes in grouped.items()
    ]


def get_routing_state(session: Session) -> list[dict]:
    rules = session.scalars(select(RoutingRule).order_by(RoutingRule.priority_class, RoutingRule.rule_id)).all()
    rule_nodes = session.scalars(select(RoutingRuleNode).order_by(RoutingRuleNode.rule_id, RoutingRuleNode.sort_order)).all()
    nodes_by_rule: dict[str, list[str]] = defaultdict(list)
    for rule_node in rule_nodes:
        nodes_by_rule[rule_node.rule_id].append(rule_node.node_id)
    return [
        {
            "rule_id": rule.rule_id,
            "priority_class": rule.priority_class,
            "model_name": rule.model_name,
            "preferred_nodes": nodes_by_rule.get(rule.rule_id, []),
        }
        for rule in rules
    ]


def get_warnings_state(session: Session) -> list[dict]:
    warnings = session.scalars(
        select(WarningRecord).where(WarningRecord.status == "active").order_by(WarningRecord.last_seen_at.desc())
    ).all()
    return [
        {
            "warning_id": warning.warning_id,
            "warning_type": warning.warning_type,
            "severity": warning.severity,
            "node_id": warning.node_id,
            "summary": warning.summary,
        }
        for warning in warnings
    ]


def build_full_state(session: Session, config: BootstrapConfig | None = None) -> dict:
    return {
        "nodes": get_nodes_state(session, config=config),
        "runs": get_runs_state(session),
        "models": get_models_state(session),
        "routing": get_routing_state(session),
        "warnings": get_warnings_state(session),
    }
