import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.config import BootstrapConfig, BootstrapNode
from backend.app.models import Base, ModelPlacement, Node, NodeSnapshot, WarningRecord
from backend.app.services.runtime import run_poll_cycle
from backend.app.services.state import get_nodes_state


def build_session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_run_poll_cycle_persists_snapshots_and_model_inventory(monkeypatch) -> None:
    session_factory = build_session_factory()
    config = BootstrapConfig(
        local_ollama_base_urls=["http://127.0.0.1:11434", "http://127.0.0.1:11435"],
        nodes=[
            BootstrapNode(
                node_id="jedi",
                display_name="Jedi",
                base_url="http://127.0.0.1:8000",
                role="primary",
                enabled=True,
            )
        ],
    )

    with session_factory() as session:
        session.add(
            Node(
                node_id="jedi",
                display_name="Jedi",
                base_url="http://127.0.0.1:8000",
                role="primary",
                enabled=True,
                created_from="bootstrap",
            )
        )
        session.commit()

    async def fake_collect(node, runtime_config):
        assert runtime_config.local_ollama_base_urls == ["http://127.0.0.1:11434", "http://127.0.0.1:11435"]
        return {
            "node_id": node.node_id,
            "captured_at": datetime.now(UTC),
            "gpu_json": [],
            "cpu_json": {"usage_percent": 8},
            "memory_json": {"used_mb": 4096},
            "ollama_json": {
                "status": "ok",
                "models": [{"name": "qwen3.5:27b", "digest": "sha256:111"}],
                "errors": [],
            },
        }

    monkeypatch.setattr("backend.app.services.runtime.collect_snapshot_for_node", fake_collect)

    state = asyncio.run(run_poll_cycle(config, session_factory=session_factory))

    assert state["models"] == [{"model_name": "qwen3.5:27b", "placements": ["jedi"]}]
    assert state["nodes"][0]["model_count"] == 1
    assert state["nodes"][0]["ollama_status"] == "ok"
    assert state["nodes"][0]["memory_used_mb"] == 4096

    with session_factory() as session:
        node = session.get(Node, "jedi")
        placements = session.scalars(select(ModelPlacement)).all()

    assert node is not None
    assert node.last_seen_at is not None
    assert len(placements) == 1
    assert placements[0].model_name == "qwen3.5:27b"


def test_get_nodes_state_marks_old_observation_as_unreachable() -> None:
    session_factory = build_session_factory()
    with session_factory() as session:
        stale_time = datetime.now(UTC) - timedelta(seconds=45)
        session.add(
            Node(
                node_id="bastet",
                display_name="Bastet",
                base_url="http://192.168.50.209:9100",
                role="remote",
                enabled=True,
                created_from="bootstrap",
                last_seen_at=stale_time,
            )
        )
        session.add(
            NodeSnapshot(
                node_id="bastet",
                captured_at=stale_time,
                gpu_json=[],
                cpu_json={},
                memory_json={},
                ollama_json={"status": "ok", "models": []},
                health_status="healthy",
            )
        )
        session.commit()

        state = get_nodes_state(
            session,
            config=BootstrapConfig(stale_after_seconds=15, unreachable_after_seconds=30),
        )

    assert state[0]["observed_status"] == "unreachable"
    assert state[0]["freshness"] == "stale"
    assert state[0]["gpu_stats"] == []
    assert state[0]["model_count"] == 0


def test_get_nodes_state_exposes_latest_gpu_and_model_details() -> None:
    session_factory = build_session_factory()
    with session_factory() as session:
        captured_at = datetime.now(UTC)
        session.add(
            Node(
                node_id="bastet",
                display_name="Bastet",
                base_url="http://192.168.50.209:9110",
                role="remote",
                enabled=True,
                created_from="bootstrap",
                last_seen_at=captured_at,
            )
        )
        session.add(
            NodeSnapshot(
                node_id="bastet",
                captured_at=captured_at,
                gpu_json=[{"name": "RTX 3090", "memory_total_mb": 24576, "temperature_c": 42}],
                cpu_json={"usage_percent": 11},
                memory_json={"used_mb": 32768},
                ollama_json={
                    "status": "ok",
                    "models": [{"name": "qwen3.6-hermes:latest", "digest": "sha256:abc"}],
                    "errors": [],
                },
                health_status="healthy",
            )
        )
        session.commit()

        state = get_nodes_state(session, config=BootstrapConfig())

    assert state[0]["base_url"] == "http://192.168.50.209:9110"
    assert state[0]["gpu_stats"][0]["name"] == "RTX 3090"
    assert state[0]["cpu_usage_percent"] == 11
    assert state[0]["memory_used_mb"] == 32768
    assert state[0]["model_count"] == 1
    assert state[0]["ollama_status"] == "ok"


def test_run_poll_cycle_resolves_config_drift_warning_once_node_is_observed(monkeypatch) -> None:
    session_factory = build_session_factory()
    config = BootstrapConfig(
        nodes=[
            BootstrapNode(
                node_id="bastet",
                display_name="Bastet",
                base_url="http://192.168.50.209:9100",
                role="remote",
                enabled=True,
            )
        ],
    )

    with session_factory() as session:
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
        session.add(
            WarningRecord(
                warning_id="warn-1",
                warning_type="config_drift",
                severity="warning",
                node_id="bastet",
                summary="Configured node bastet has no recent observation",
                metadata_json={},
            )
        )
        session.commit()

    async def fake_collect(node, runtime_config):
        return {
            "node_id": node.node_id,
            "captured_at": datetime.now(UTC),
            "gpu_json": [],
            "cpu_json": {},
            "memory_json": {},
            "ollama_json": {
                "status": "ok",
                "models": [],
                "errors": [],
            },
        }

    monkeypatch.setattr("backend.app.services.runtime.collect_snapshot_for_node", fake_collect)

    asyncio.run(run_poll_cycle(config, session_factory=session_factory))

    with session_factory() as session:
        warning = session.get(WarningRecord, "warn-1")

    assert warning is not None
    assert warning.status == "resolved"
