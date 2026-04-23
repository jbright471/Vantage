from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select

from backend.app.db import SessionLocal
from backend.app.models import Node, RoutingRule, RoutingRuleNode
from backend.app.services.state import get_routing_state

router = APIRouter()


class RoutingRuleUpdateRequest(BaseModel):
    preferred_nodes: list[str]


@router.get("/routing")
def list_routing() -> list[dict]:
    with SessionLocal() as session:
        return get_routing_state(session)


@router.put("/routing/{rule_id}")
def update_routing(rule_id: str, payload: RoutingRuleUpdateRequest) -> dict:
    deduped_nodes: list[str] = []
    for node_id in payload.preferred_nodes:
        if node_id not in deduped_nodes:
            deduped_nodes.append(node_id)

    with SessionLocal() as session:
        rule = session.get(RoutingRule, rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail=f"Unknown routing rule '{rule_id}'")

        known_nodes = set(session.scalars(select(Node.node_id).where(Node.enabled.is_(True))).all())
        unknown_nodes = [node_id for node_id in deduped_nodes if node_id not in known_nodes]
        if unknown_nodes:
            raise HTTPException(status_code=400, detail=f"Unknown node ids: {', '.join(unknown_nodes)}")

        session.execute(delete(RoutingRuleNode).where(RoutingRuleNode.rule_id == rule_id))
        for sort_order, node_id in enumerate(deduped_nodes):
            session.add(RoutingRuleNode(rule_id=rule_id, node_id=node_id, sort_order=sort_order))
        session.commit()

        updated = next((item for item in get_routing_state(session) if item["rule_id"] == rule_id), None)

    if updated is None:
        raise HTTPException(status_code=404, detail=f"Routing rule '{rule_id}' disappeared during update")
    return updated
