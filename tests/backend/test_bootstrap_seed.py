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


def test_seed_nodes_from_config_updates_existing_bootstrap_node_fields() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            Node(
                node_id="bastet",
                display_name="Bastet",
                base_url="http://192.168.50.209:9100",
                role="remote",
                enabled=True,
                created_from="bootstrap",
            )
        )
        session.commit()

        config = BootstrapConfig(
            nodes=[
                BootstrapNode(
                    node_id="bastet",
                    display_name="Bastet",
                    base_url="http://192.168.50.209:9110",
                    role="remote",
                    enabled=True,
                )
            ]
        )

        seed_nodes_from_config(session, config)
        updated = session.get(Node, "bastet")

    assert updated is not None
    assert updated.base_url == "http://192.168.50.209:9110"
