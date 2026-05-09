from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import BootstrapConfig
from backend.app.models import ModelPlacement, Node, NodeSnapshot, RoutingRule, RoutingRuleHistory, RoutingRuleNode, Run


def _timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped


def _latest_snapshots_by_node(session: Session) -> dict[str, NodeSnapshot]:
    snapshots = session.scalars(select(NodeSnapshot).order_by(NodeSnapshot.captured_at.desc())).all()
    latest_by_node: dict[str, NodeSnapshot] = {}
    for snapshot in snapshots:
        latest_by_node.setdefault(snapshot.node_id, snapshot)
    return latest_by_node


def _model_available_by_node(session: Session, model_name: str | None) -> dict[str, bool]:
    if not model_name:
        return {}

    placements = session.scalars(
        select(ModelPlacement).where(ModelPlacement.model_name == model_name).order_by(ModelPlacement.node_id)
    ).all()
    return {placement.node_id: placement.available for placement in placements}


def serialize_routing_rule(session: Session, rule: RoutingRule) -> dict:
    preferred_nodes = session.scalars(
        select(RoutingRuleNode.node_id)
        .where(RoutingRuleNode.rule_id == rule.rule_id)
        .order_by(RoutingRuleNode.sort_order)
    ).all()
    return {
        "rule_id": rule.rule_id,
        "priority_class": rule.priority_class,
        "model_name": rule.model_name,
        "enabled": rule.enabled,
        "allow_degraded": rule.allow_degraded,
        "allow_stale": rule.allow_stale,
        "allow_unreachable": rule.allow_unreachable,
        "minimum_eval_pass_rate": rule.minimum_eval_pass_rate,
        "preferred_nodes": list(preferred_nodes),
    }


def record_routing_history(
    session: Session,
    *,
    rule_id: str,
    action_type: str,
    summary: str,
    before: dict | None,
    after: dict | None,
) -> None:
    session.add(
        RoutingRuleHistory(
            rule_id=rule_id,
            action_type=action_type,
            summary=summary,
            before_json=before,
            after_json=after,
        )
    )


def _eval_pass_rates_by_node(session: Session, model_name: str | None) -> dict[str, float]:
    if not model_name:
        return {}

    runs = session.scalars(
        select(Run).where(
            Run.source_type == "eval",
            Run.detail_type == "eval_attempt",
            Run.model_name == model_name,
        )
    ).all()
    totals: dict[str, int] = {}
    passes: dict[str, int] = {}
    for run in runs:
        score = (run.metadata_json or {}).get("score")
        if not isinstance(score, dict) or not isinstance(score.get("passed"), bool):
            continue
        totals[run.node_id] = totals.get(run.node_id, 0) + 1
        if score["passed"]:
            passes[run.node_id] = passes.get(run.node_id, 0) + 1

    return {node_id: round(passes.get(node_id, 0) / total, 4) for node_id, total in totals.items() if total > 0}


def simulate_routing_rule(
    session: Session,
    rule: RoutingRule,
    preferred_nodes: list[str],
    config: BootstrapConfig,
    model_name: str | None = None,
) -> dict:
    candidate_order = _dedupe(preferred_nodes)
    nodes = {node.node_id: node for node in session.scalars(select(Node)).all()}
    latest_snapshots = _latest_snapshots_by_node(session)
    effective_model_name = model_name if model_name is not None else rule.model_name
    model_availability = _model_available_by_node(session, effective_model_name)
    eval_pass_rates = _eval_pass_rates_by_node(session, effective_model_name)
    now = datetime.now(UTC)

    decisions: list[dict] = []
    selected_node: str | None = None
    warnings: list[str] = []

    if not rule.enabled:
        warnings.append("Routing rule is disabled. No node will be selected until the rule is enabled.")

    for node_id in candidate_order:
        node = nodes.get(node_id)
        reasons: list[str] = []
        observed_status = "unknown"
        freshness = "unknown"
        signal_age_seconds: float | None = None
        model_available: bool | None = None
        eval_pass_rate: float | None = None

        if node is None:
            reasons.append("unknown_node")
            decisions.append(
                {
                    "node_id": node_id,
                    "display_name": node_id,
                    "decision": "rejected",
                    "observed_status": observed_status,
                    "freshness": freshness,
                    "signal_age_seconds": signal_age_seconds,
                    "model_available": model_available,
                    "eval_pass_rate": eval_pass_rate,
                    "reasons": reasons,
                }
            )
            continue

        latest_snapshot = latest_snapshots.get(node_id)
        last_seen_at = _timestamp(node.last_seen_at)
        if last_seen_at is not None:
            signal_age_seconds = max(0, (now - last_seen_at).total_seconds())
            freshness = "stale" if signal_age_seconds >= config.stale_after_seconds else "live"
            if signal_age_seconds < config.unreachable_after_seconds and latest_snapshot is not None:
                observed_status = latest_snapshot.health_status
            else:
                observed_status = "unreachable"
        else:
            observed_status = "unreachable"
            freshness = "stale"

        if not rule.enabled:
            reasons.append("rule_disabled")
        if not node.enabled:
            reasons.append("node_disabled")
        if observed_status == "degraded" and rule.allow_degraded:
            reasons.append("allowed_health:degraded")
        elif observed_status == "unreachable" and rule.allow_unreachable:
            reasons.append("allowed_health:unreachable")
        elif observed_status != "healthy":
            reasons.append(f"health:{observed_status}")
        if freshness != "live" and rule.allow_stale:
            reasons.append(f"allowed_freshness:{freshness}")
        elif freshness != "live":
            reasons.append(f"freshness:{freshness}")
        if effective_model_name:
            model_available = model_availability.get(node_id, False)
            if not model_available:
                reasons.append(f"model_missing:{effective_model_name}")
            eval_pass_rate = eval_pass_rates.get(node_id)
            if rule.minimum_eval_pass_rate is not None and eval_pass_rate is not None:
                if eval_pass_rate < rule.minimum_eval_pass_rate:
                    reasons.append(f"eval_pass_rate_below_minimum:{eval_pass_rate:.4f}<{rule.minimum_eval_pass_rate:.4f}")

        blocking_reasons = [reason for reason in reasons if not reason.startswith("allowed_")]
        if selected_node is None and not blocking_reasons:
            selected_node = node_id
            decision = "selected"
            reasons.append("selected:first_eligible")
        elif not blocking_reasons:
            decision = "skipped"
            reasons.append("lower_priority_than_selected")
        else:
            decision = "rejected"

        decisions.append(
            {
                "node_id": node_id,
                "display_name": node.display_name,
                "decision": decision,
                "observed_status": observed_status,
                "freshness": freshness,
                "signal_age_seconds": signal_age_seconds,
                "model_available": model_available,
                "eval_pass_rate": eval_pass_rate,
                "reasons": reasons,
            }
        )

    if selected_node is None:
        warnings.append(
            "No eligible node satisfies the current health, freshness, enabled-state, model, and eval constraints."
        )
    elif candidate_order and selected_node != candidate_order[0]:
        warnings.append(f"Preferred node '{candidate_order[0]}' would be skipped; '{selected_node}' is first eligible.")

    return {
        "rule_id": rule.rule_id,
        "priority_class": rule.priority_class,
        "model_name": effective_model_name,
        "candidate_order": candidate_order,
        "selected_node": selected_node,
        "decisions": decisions,
        "warnings": warnings,
        "policy": {
            "allow_degraded": rule.allow_degraded,
            "allow_stale": rule.allow_stale,
            "allow_unreachable": rule.allow_unreachable,
            "minimum_eval_pass_rate": rule.minimum_eval_pass_rate,
        },
    }
