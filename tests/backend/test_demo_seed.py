import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.config import BootstrapConfig
from backend.app.models import Base, Node, RoutingRule, Run
from backend.app.services.demo import seed_demo_data
from backend.app.services.state import build_full_state


def build_session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_seed_demo_data_populates_safe_shareable_state() -> None:
    session_factory = build_session_factory()

    with session_factory() as session:
        seed_demo_data(session)
        state = build_full_state(session, config=BootstrapConfig(stale_after_seconds=30, unreachable_after_seconds=60))

    assert {node["node_id"] for node in state["nodes"]} >= {"demo-control", "demo-worker"}
    assert {run["run_id"] for run in state["runs"]} >= {
        "demo-run-capability-ok",
        "demo-run-routing-dry-run",
        "demo-run-eval-failed",
    }
    assert {model["model_name"] for model in state["models"]} >= {"llama3.1:8b", "qwen2.5-coder:14b"}
    assert any(rule["rule_id"] == "demo-interactive-local-first" for rule in state["routing"])
    assert any(warning["warning_id"] == "demo-warning-worker-degraded" for warning in state["warnings"])
    assert "192.168." not in json.dumps(state)
    assert "C:\\Users" not in json.dumps(state)


def test_seed_demo_data_is_idempotent() -> None:
    session_factory = build_session_factory()

    with session_factory() as session:
        seed_demo_data(session)
        seed_demo_data(session)

        demo_nodes = session.scalars(select(Node).where(Node.node_id.in_(["demo-control", "demo-worker"]))).all()
        demo_runs = session.scalars(select(Run).where(Run.run_id.like("demo-run-%"))).all()
        demo_rules = session.scalars(select(RoutingRule).where(RoutingRule.rule_id.like("demo-%"))).all()

    assert len(demo_nodes) == 2
    assert len(demo_runs) == 3
    assert len(demo_rules) == 2
