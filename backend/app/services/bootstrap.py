from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import BootstrapConfig
from backend.app.models import Node


def seed_nodes_from_config(session: Session, config: BootstrapConfig) -> None:
    for bootstrap_node in config.nodes:
        existing = session.scalar(select(Node).where(Node.node_id == bootstrap_node.node_id))
        if existing:
            continue
        session.add(
            Node(
                node_id=bootstrap_node.node_id,
                display_name=bootstrap_node.display_name,
                base_url=bootstrap_node.base_url,
                role=bootstrap_node.role,
                enabled=bootstrap_node.enabled,
                created_from="bootstrap",
            )
        )
    session.commit()
