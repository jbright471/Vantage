from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import ModelPlacement, Node, RoutingRule, RoutingRuleNode, Run, WarningRecord


def get_nodes_state(session: Session) -> list[dict]:
    nodes = session.scalars(select(Node).order_by(Node.display_name)).all()
    state: list[dict] = []
    for node in nodes:
        state.append(
            {
                "node_id": node.node_id,
                "display_name": node.display_name,
                "role": node.role,
                "enabled": node.enabled,
                "created_from": node.created_from,
                "observed_status": "unreachable" if node.last_seen_at is None else "healthy",
                "freshness": "stale" if node.last_seen_at is None else "live",
                "last_seen_at": node.last_seen_at.isoformat() if node.last_seen_at else None,
            }
        )
    return state


def get_runs_state(session: Session) -> list[dict]:
    runs = session.scalars(select(Run).order_by(Run.started_at.desc())).all()
    return [
        {
            "run_id": run.run_id,
            "summary": run.summary,
            "status": run.status,
            "node_id": run.node_id,
            "started_at": run.started_at.isoformat(),
        }
        for run in runs
    ]


def get_models_state(session: Session) -> list[dict]:
    placements = session.scalars(select(ModelPlacement).order_by(ModelPlacement.model_name, ModelPlacement.node_id)).all()
    grouped: dict[str, list[str]] = defaultdict(list)
    for placement in placements:
        grouped[placement.model_name].append(placement.node_id)
    return [{"model_name": model_name, "placements": nodes} for model_name, nodes in grouped.items()]


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


def build_full_state(session: Session) -> dict:
    return {
        "nodes": get_nodes_state(session),
        "runs": get_runs_state(session),
        "models": get_models_state(session),
        "routing": get_routing_state(session),
        "warnings": get_warnings_state(session),
    }
