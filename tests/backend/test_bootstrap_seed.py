from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.config import BootstrapConfig, BootstrapNode
from backend.app.models import Base, Node
from backend.app.services.bootstrap import seed_nodes_from_config


def test_seed_nodes_from_config_inserts_without_duplicates() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    config = BootstrapConfig(
        nodes=[
            BootstrapNode(
                node_id="jedi",
                display_name="Jedi",
                base_url="http://127.0.0.1:8000",
                role="primary",
                enabled=True,
            )
        ]
    )

    with Session(engine) as session:
        seed_nodes_from_config(session, config)
        seed_nodes_from_config(session, config)
        nodes = session.scalars(select(Node)).all()

    assert len(nodes) == 1
    assert nodes[0].created_from == "bootstrap"
    assert {
        "nodes",
        "node_snapshots",
        "runs",
        "model_placements",
        "routing_rules",
        "routing_rule_nodes",
        "app_settings",
        "warning_records",
    }.issubset(Base.metadata.tables.keys())
