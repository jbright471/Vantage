from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select

from backend.app.config import DEFAULT_BOOTSTRAP_CONFIG_PATH, load_bootstrap_config
from backend.app.db import SessionLocal
from backend.app.models import Node, RoutingRule, RoutingRuleHistory, RoutingRuleNode
from backend.app.services.routing import record_routing_history, serialize_routing_rule, simulate_routing_rule
from backend.app.services.state import get_routing_state

router = APIRouter()


class RoutingRuleUpdateRequest(BaseModel):
    preferred_nodes: list[str]


class RoutingRuleCreateRequest(BaseModel):
    rule_id: str
    priority_class: str
    model_name: str | None = None
    preferred_nodes: list[str]
    enabled: bool = True
    allow_degraded: bool = False
    allow_stale: bool = False
    allow_unreachable: bool = False
    minimum_eval_pass_rate: float | None = None


class RoutingRulePatchRequest(BaseModel):
    priority_class: str | None = None
    model_name: str | None = None
    preferred_nodes: list[str] | None = None
    enabled: bool | None = None
    allow_degraded: bool | None = None
    allow_stale: bool | None = None
    allow_unreachable: bool | None = None
    minimum_eval_pass_rate: float | None = None


class RoutingRuleDryRunRequest(BaseModel):
    preferred_nodes: list[str] | None = None
    model_name: str | None = None


@router.get("/routing")
def list_routing() -> list[dict]:
    with SessionLocal() as session:
        return get_routing_state(session)


def _dedupe_nodes(nodes: list[str]) -> list[str]:
    deduped_nodes: list[str] = []
    for node_id in nodes:
        if node_id not in deduped_nodes:
            deduped_nodes.append(node_id)
    return deduped_nodes


def _validate_node_ids(session, node_ids: list[str]) -> None:
    known_nodes = set(session.scalars(select(Node.node_id)).all())
    unknown_nodes = [node_id for node_id in node_ids if node_id not in known_nodes]
    if unknown_nodes:
        raise HTTPException(status_code=400, detail=f"Unknown node ids: {', '.join(unknown_nodes)}")


def _replace_rule_nodes(session, rule_id: str, node_ids: list[str]) -> None:
    session.execute(delete(RoutingRuleNode).where(RoutingRuleNode.rule_id == rule_id))
    for sort_order, node_id in enumerate(node_ids):
        session.add(RoutingRuleNode(rule_id=rule_id, node_id=node_id, sort_order=sort_order))


@router.post("/routing")
def create_routing(payload: RoutingRuleCreateRequest) -> dict:
    preferred_nodes = _dedupe_nodes(payload.preferred_nodes)
    with SessionLocal() as session:
        existing = session.get(RoutingRule, payload.rule_id)
        if existing is not None:
            raise HTTPException(status_code=409, detail=f"Routing rule '{payload.rule_id}' already exists")
        _validate_node_ids(session, preferred_nodes)

        rule = RoutingRule(
            rule_id=payload.rule_id,
            priority_class=payload.priority_class,
            model_name=payload.model_name,
            enabled=payload.enabled,
            allow_degraded=payload.allow_degraded,
            allow_stale=payload.allow_stale,
            allow_unreachable=payload.allow_unreachable,
            minimum_eval_pass_rate=payload.minimum_eval_pass_rate,
        )
        session.add(rule)
        _replace_rule_nodes(session, payload.rule_id, preferred_nodes)
        session.flush()
        after = serialize_routing_rule(session, rule)
        record_routing_history(
            session,
            rule_id=payload.rule_id,
            action_type="create",
            summary=f"Created routing rule {payload.rule_id}",
            before=None,
            after=after,
        )
        session.commit()
        return after


@router.get("/routing/{rule_id}/history")
def list_routing_history(rule_id: str) -> list[dict]:
    with SessionLocal() as session:
        history = session.scalars(
            select(RoutingRuleHistory)
            .where(RoutingRuleHistory.rule_id == rule_id)
            .order_by(RoutingRuleHistory.changed_at.desc(), RoutingRuleHistory.history_id.desc())
            .limit(50)
        ).all()
        return [
            {
                "history_id": item.history_id,
                "rule_id": item.rule_id,
                "action_type": item.action_type,
                "changed_at": item.changed_at.isoformat(),
                "summary": item.summary,
                "before_json": item.before_json,
                "after_json": item.after_json,
            }
            for item in history
        ]


@router.post("/routing/{rule_id}/dry-run")
def dry_run_routing(rule_id: str, payload: RoutingRuleDryRunRequest) -> dict:
    with SessionLocal() as session:
        rule = session.get(RoutingRule, rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail=f"Unknown routing rule '{rule_id}'")

        if payload.preferred_nodes is None:
            current_nodes = session.scalars(
                select(RoutingRuleNode.node_id)
                .where(RoutingRuleNode.rule_id == rule_id)
                .order_by(RoutingRuleNode.sort_order)
            ).all()
            preferred_nodes = list(current_nodes)
        else:
            preferred_nodes = payload.preferred_nodes

        known_nodes = set(session.scalars(select(Node.node_id)).all())
        unknown_nodes = [node_id for node_id in preferred_nodes if node_id not in known_nodes]
        if unknown_nodes:
            raise HTTPException(status_code=400, detail=f"Unknown node ids: {', '.join(unknown_nodes)}")

        config = load_bootstrap_config(DEFAULT_BOOTSTRAP_CONFIG_PATH)
        return simulate_routing_rule(
            session,
            rule,
            preferred_nodes=preferred_nodes,
            config=config,
            model_name=payload.model_name,
        )


@router.put("/routing/{rule_id}")
def update_routing(rule_id: str, payload: RoutingRuleUpdateRequest) -> dict:
    deduped_nodes = _dedupe_nodes(payload.preferred_nodes)

    with SessionLocal() as session:
        rule = session.get(RoutingRule, rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail=f"Unknown routing rule '{rule_id}'")

        _validate_node_ids(session, deduped_nodes)

        before = serialize_routing_rule(session, rule)
        _replace_rule_nodes(session, rule_id, deduped_nodes)
        session.flush()
        after = serialize_routing_rule(session, rule)
        record_routing_history(
            session,
            rule_id=rule_id,
            action_type="update",
            summary=f"Updated preferred order for routing rule {rule_id}",
            before=before,
            after=after,
        )
        session.commit()

        updated = next((item for item in get_routing_state(session) if item["rule_id"] == rule_id), None)

    if updated is None:
        raise HTTPException(status_code=404, detail=f"Routing rule '{rule_id}' disappeared during update")
    return updated


@router.patch("/routing/{rule_id}")
def patch_routing(rule_id: str, payload: RoutingRulePatchRequest) -> dict:
    with SessionLocal() as session:
        rule = session.get(RoutingRule, rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail=f"Unknown routing rule '{rule_id}'")

        before = serialize_routing_rule(session, rule)
        if payload.priority_class is not None:
            rule.priority_class = payload.priority_class
        if payload.model_name is not None:
            rule.model_name = payload.model_name or None
        if payload.enabled is not None:
            rule.enabled = payload.enabled
        if payload.allow_degraded is not None:
            rule.allow_degraded = payload.allow_degraded
        if payload.allow_stale is not None:
            rule.allow_stale = payload.allow_stale
        if payload.allow_unreachable is not None:
            rule.allow_unreachable = payload.allow_unreachable
        if payload.minimum_eval_pass_rate is not None:
            rule.minimum_eval_pass_rate = payload.minimum_eval_pass_rate
        if payload.preferred_nodes is not None:
            preferred_nodes = _dedupe_nodes(payload.preferred_nodes)
            _validate_node_ids(session, preferred_nodes)
            _replace_rule_nodes(session, rule_id, preferred_nodes)

        session.flush()
        after = serialize_routing_rule(session, rule)
        record_routing_history(
            session,
            rule_id=rule_id,
            action_type="update",
            summary=f"Updated routing rule {rule_id}",
            before=before,
            after=after,
        )
        session.commit()
        return after


@router.delete("/routing/{rule_id}")
def delete_routing(rule_id: str) -> dict:
    with SessionLocal() as session:
        rule = session.get(RoutingRule, rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail=f"Unknown routing rule '{rule_id}'")

        before = serialize_routing_rule(session, rule)
        session.execute(delete(RoutingRuleNode).where(RoutingRuleNode.rule_id == rule_id))
        session.delete(rule)
        record_routing_history(
            session,
            rule_id=rule_id,
            action_type="delete",
            summary=f"Deleted routing rule {rule_id}",
            before=before,
            after=None,
        )
        session.commit()
        return {"rule_id": rule_id, "deleted": True}
