from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import BootstrapConfig
from backend.app.models import AppSetting, Node, RoutingRule, RoutingRuleNode

NODE_ENABLED_OVERRIDES_KEY = "node_enabled_overrides"


def get_node_enabled_overrides(session: Session) -> dict[str, bool]:
    setting = session.get(AppSetting, NODE_ENABLED_OVERRIDES_KEY)
    if setting is None:
        return {}
    nodes = setting.value_json.get("nodes", {})
    if not isinstance(nodes, dict):
        return {}
    return {str(node_id): bool(enabled) for node_id, enabled in nodes.items()}


def seed_nodes_from_config(session: Session, config: BootstrapConfig) -> None:
    enabled_overrides = get_node_enabled_overrides(session)
    for bootstrap_node in config.nodes:
        enabled = enabled_overrides.get(bootstrap_node.node_id, bootstrap_node.enabled)
        existing = session.scalar(select(Node).where(Node.node_id == bootstrap_node.node_id))
        if existing:
            if existing.created_from == "bootstrap":
                existing.display_name = bootstrap_node.display_name
                existing.base_url = bootstrap_node.base_url
                existing.role = bootstrap_node.role
                existing.enabled = enabled
            continue
        session.add(
            Node(
                node_id=bootstrap_node.node_id,
                display_name=bootstrap_node.display_name,
                base_url=bootstrap_node.base_url,
                role=bootstrap_node.role,
                enabled=enabled,
                created_from="bootstrap",
            )
        )
    session.commit()


def _default_routing_specs(config: BootstrapConfig) -> list[dict]:
    enabled_nodes = [node for node in config.nodes if node.enabled]
    if not enabled_nodes:
        return []

    primary_nodes = [node.node_id for node in enabled_nodes if node.role == "primary"]
    worker_nodes = [node.node_id for node in enabled_nodes if node.role != "primary"]
    control_first = primary_nodes + worker_nodes
    worker_first = worker_nodes + primary_nodes if worker_nodes else control_first

    return [
        {
            "rule_id": "interactive-default",
            "priority_class": "interactive",
            "model_name": None,
            "preferred_nodes": control_first,
        },
        {
            "rule_id": "batch-default",
            "priority_class": "batch",
            "model_name": None,
            "preferred_nodes": worker_first,
        },
        {
            "rule_id": "scheduled-default",
            "priority_class": "scheduled",
            "model_name": None,
            "preferred_nodes": worker_first,
        },
    ]


def seed_routing_from_config(session: Session, config: BootstrapConfig) -> None:
    existing_rule_ids = set(session.scalars(select(RoutingRule.rule_id)).all())
    for spec in _default_routing_specs(config):
        if spec["rule_id"] in existing_rule_ids:
            continue

        session.add(
            RoutingRule(
                rule_id=spec["rule_id"],
                priority_class=spec["priority_class"],
                model_name=spec["model_name"],
                enabled=True,
            )
        )
        for sort_order, node_id in enumerate(spec["preferred_nodes"]):
            session.add(RoutingRuleNode(rule_id=spec["rule_id"], node_id=node_id, sort_order=sort_order))

    session.commit()
