from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import BootstrapConfig
from backend.app.models import ModelPlacement, Node, NodeSnapshot, RoutingRule, RoutingRuleHistory, RoutingRuleNode, Run

EVAL_EVIDENCE_VALIDATED = "validated"
EVAL_EVIDENCE_FAILED = "failed"
EVAL_EVIDENCE_UNVERIFIED = "unverified"
EVAL_EVIDENCE_STALE = "stale"

# Reasons that describe an accepted condition rather than a blocking one. Every other
# reason recorded on a decision keeps the node out of the selection.
NON_BLOCKING_REASON_PREFIXES = ("allowed_", "eval_evidence_note:")


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
        "allow_unverified": rule.allow_unverified,
        "allow_stale_evidence": rule.allow_stale_evidence,
        "minimum_eval_pass_rate": rule.minimum_eval_pass_rate,
        "required_eval_suite_id": rule.required_eval_suite_id,
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


def _current_model_digests_by_node(session: Session, model_name: str | None) -> dict[str, str]:
    """Digest of the artifact each node currently serves for ``model_name``.

    Evaluation evidence is only attributable to the artifact it ran against, so a run's
    recorded digest has to match the digest the node is serving now. Nodes whose placement
    carries no digest are absent from this mapping and skip digest scoping entirely.
    """
    if not model_name:
        return {}

    placements = session.scalars(
        select(ModelPlacement)
        .where(ModelPlacement.model_name == model_name)
        .order_by(ModelPlacement.last_seen_at.asc(), ModelPlacement.placement_id.asc())
    ).all()
    digests: dict[str, str] = {}
    for placement in placements:
        if placement.available and placement.model_digest:
            digests[placement.node_id] = placement.model_digest
    return digests


def _eval_evidence_by_node(
    session: Session,
    *,
    model_name: str | None,
    suite_id: str | None,
    expected_digests: dict[str, str],
    now: datetime,
    max_age_seconds: int,
) -> dict[str, dict]:
    """Aggregate scored eval attempts per node, scoped to suite, digest, and recency.

    Attempts outside the recency window are tallied separately so a node whose only
    evidence has expired can be reported as stale instead of silently counting as current.
    """
    if not model_name:
        return {}

    runs = session.scalars(
        select(Run).where(
            Run.source_type == "eval",
            Run.detail_type == "eval_attempt",
            Run.model_name == model_name,
        )
    ).all()

    evidence: dict[str, dict] = {}
    for run in runs:
        metadata = run.metadata_json or {}
        score = metadata.get("score")
        if not isinstance(score, dict) or not isinstance(score.get("passed"), bool):
            continue
        if suite_id is not None and metadata.get("suite_id") != suite_id:
            continue
        expected_digest = expected_digests.get(run.node_id)
        if expected_digest is not None and metadata.get("model_digest") != expected_digest:
            continue

        started_at = _timestamp(run.started_at)
        age_seconds = None if started_at is None else max(0.0, (now - started_at).total_seconds())
        within_window = age_seconds is not None and age_seconds <= max_age_seconds

        bucket = evidence.setdefault(
            run.node_id,
            {
                "fresh_total": 0,
                "fresh_passes": 0,
                "stale_total": 0,
                "stale_passes": 0,
                "latest_age_seconds": None,
                "latest_run_at": None,
            },
        )
        if within_window:
            bucket["fresh_total"] += 1
            if score["passed"]:
                bucket["fresh_passes"] += 1
        else:
            bucket["stale_total"] += 1
            if score["passed"]:
                bucket["stale_passes"] += 1

        if age_seconds is not None and (
            bucket["latest_age_seconds"] is None or age_seconds < bucket["latest_age_seconds"]
        ):
            bucket["latest_age_seconds"] = age_seconds
            bucket["latest_run_at"] = started_at.isoformat() if started_at is not None else None

    return evidence


def _resolve_eval_evidence(bucket: dict | None, minimum: float | None) -> tuple[str, float | None, int]:
    """Classify a node's in-scope evidence into one of the four evidence states."""
    if bucket is None or (bucket["fresh_total"] == 0 and bucket["stale_total"] == 0):
        return EVAL_EVIDENCE_UNVERIFIED, None, 0

    if bucket["fresh_total"] > 0:
        pass_rate = round(bucket["fresh_passes"] / bucket["fresh_total"], 4)
        if minimum is not None and pass_rate < minimum:
            return EVAL_EVIDENCE_FAILED, pass_rate, bucket["fresh_total"]
        return EVAL_EVIDENCE_VALIDATED, pass_rate, bucket["fresh_total"]

    pass_rate = round(bucket["stale_passes"] / bucket["stale_total"], 4)
    return EVAL_EVIDENCE_STALE, pass_rate, bucket["stale_total"]


def _eval_evidence_reasons(
    *,
    state: str,
    pass_rate: float | None,
    minimum: float | None,
    allow_unverified: bool,
    allow_stale_evidence: bool,
) -> list[str]:
    """Reason strings for an evidence state.

    ``unverified`` and ``stale`` block by default; an operator opts into them explicitly.
    When no minimum is configured the rule is not asking for evidence at all, so the state
    is still reported but never blocks.
    """
    if state == EVAL_EVIDENCE_VALIDATED:
        return ["eval_evidence_note:validated"]

    if minimum is None:
        return [f"eval_evidence_note:{state}_not_enforced"]

    if state == EVAL_EVIDENCE_FAILED:
        return [
            "eval_evidence:failed",
            f"eval_pass_rate_below_minimum:{pass_rate:.4f}<{minimum:.4f}",
        ]

    if state == EVAL_EVIDENCE_UNVERIFIED:
        return ["allowed_eval_evidence:unverified"] if allow_unverified else ["eval_evidence:unverified"]

    if not allow_stale_evidence:
        return ["eval_evidence:stale"]

    # Accepting expired evidence is not the same as accepting failing evidence: an opted-in
    # stale pass rate below the configured minimum still blocks.
    reasons = ["allowed_eval_evidence:stale"]
    if pass_rate is not None and pass_rate < minimum:
        reasons.append(f"eval_pass_rate_below_minimum:{pass_rate:.4f}<{minimum:.4f}")
    return reasons


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
    expected_digests = _current_model_digests_by_node(session, effective_model_name)
    now = datetime.now(UTC)
    eval_evidence = _eval_evidence_by_node(
        session,
        model_name=effective_model_name,
        suite_id=rule.required_eval_suite_id,
        expected_digests=expected_digests,
        now=now,
        max_age_seconds=config.eval_evidence_max_age_seconds,
    )

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
        eval_evidence_state: str | None = None
        eval_evidence_sample_size: int | None = None
        eval_evidence_age_seconds: float | None = None
        eval_evidence_last_run_at: str | None = None
        eval_evidence_suite_id: str | None = None
        eval_evidence_model_digest: str | None = None

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
                    "eval_evidence_state": eval_evidence_state,
                    "eval_evidence_sample_size": eval_evidence_sample_size,
                    "eval_evidence_age_seconds": eval_evidence_age_seconds,
                    "eval_evidence_last_run_at": eval_evidence_last_run_at,
                    "eval_evidence_suite_id": eval_evidence_suite_id,
                    "eval_evidence_model_digest": eval_evidence_model_digest,
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

            bucket = eval_evidence.get(node_id)
            eval_evidence_state, eval_pass_rate, eval_evidence_sample_size = _resolve_eval_evidence(
                bucket, rule.minimum_eval_pass_rate
            )
            eval_evidence_age_seconds = bucket["latest_age_seconds"] if bucket is not None else None
            eval_evidence_last_run_at = bucket["latest_run_at"] if bucket is not None else None
            eval_evidence_suite_id = rule.required_eval_suite_id
            eval_evidence_model_digest = expected_digests.get(node_id)
            reasons.extend(
                _eval_evidence_reasons(
                    state=eval_evidence_state,
                    pass_rate=eval_pass_rate,
                    minimum=rule.minimum_eval_pass_rate,
                    allow_unverified=rule.allow_unverified,
                    allow_stale_evidence=rule.allow_stale_evidence,
                )
            )

        blocking_reasons = [reason for reason in reasons if not reason.startswith(NON_BLOCKING_REASON_PREFIXES)]
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
                "eval_evidence_state": eval_evidence_state,
                "eval_evidence_sample_size": eval_evidence_sample_size,
                "eval_evidence_age_seconds": eval_evidence_age_seconds,
                "eval_evidence_last_run_at": eval_evidence_last_run_at,
                "eval_evidence_suite_id": eval_evidence_suite_id,
                "eval_evidence_model_digest": eval_evidence_model_digest,
                "reasons": reasons,
            }
        )

    if selected_node is None:
        warnings.append(
            "No eligible node satisfies the current health, freshness, enabled-state, model, and eval constraints."
        )
    elif candidate_order and selected_node != candidate_order[0]:
        warnings.append(f"Preferred node '{candidate_order[0]}' would be skipped; '{selected_node}' is first eligible.")

    unverified_nodes = [
        decision["node_id"] for decision in decisions if decision["eval_evidence_state"] == EVAL_EVIDENCE_UNVERIFIED
    ]
    if unverified_nodes and rule.minimum_eval_pass_rate is not None:
        verdict = "accepted" if rule.allow_unverified else "rejected"
        warnings.append(
            f"No in-scope evaluation evidence for {', '.join(unverified_nodes)}; "
            f"unverified nodes are {verdict} under this rule."
        )

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
            "allow_unverified": rule.allow_unverified,
            "allow_stale_evidence": rule.allow_stale_evidence,
            "minimum_eval_pass_rate": rule.minimum_eval_pass_rate,
            "required_eval_suite_id": rule.required_eval_suite_id,
            "eval_evidence_max_age_seconds": config.eval_evidence_max_age_seconds,
        },
    }
