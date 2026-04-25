import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.config import BootstrapConfig
from backend.app.models import Base, NodeSnapshot
from backend.app.services.pruning import PruneSummary, prune_snapshots
from backend.app.workers.pruner import run_snapshot_pruning, snapshot_pruning_worker


def build_session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_prune_snapshots_deletes_old_rows_but_keeps_latest_per_node() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)

    with Session(engine) as session:
        session.add_all(
            [
                NodeSnapshot(
                    node_id="bastet",
                    captured_at=now - timedelta(hours=30),
                    gpu_json=[],
                    cpu_json={},
                    memory_json={},
                    ollama_json={},
                    health_status="healthy",
                ),
                NodeSnapshot(
                    node_id="bastet",
                    captured_at=now,
                    gpu_json=[],
                    cpu_json={},
                    memory_json={},
                    ollama_json={},
                    health_status="healthy",
                ),
            ]
        )
        session.commit()

        summary = prune_snapshots(session, now=now, retention_hours=24, max_per_node=100, min_per_node=1)
        remaining = session.scalars(select(NodeSnapshot)).all()

    assert summary.deleted_by_age == 1
    assert len(remaining) == 1
    assert remaining[0].captured_at == now.replace(tzinfo=None)


def test_prune_snapshots_enforces_per_node_cap() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)

    with Session(engine) as session:
        for index in range(5):
            session.add(
                NodeSnapshot(
                    node_id="jedi",
                    captured_at=now - timedelta(minutes=index),
                    gpu_json=[],
                    cpu_json={},
                    memory_json={},
                    ollama_json={},
                    health_status="healthy",
                )
            )
        session.commit()

        summary = prune_snapshots(session, now=now, retention_hours=24, max_per_node=3, min_per_node=1)
        remaining = session.scalars(select(NodeSnapshot).order_by(NodeSnapshot.captured_at.desc())).all()

    assert summary.deleted_by_count == 2
    assert len(remaining) == 3
    assert remaining[0].captured_at == now.replace(tzinfo=None)


def test_prune_snapshots_respects_minimum_even_when_snapshots_are_old() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)

    with Session(engine) as session:
        for index in range(5):
            session.add(
                NodeSnapshot(
                    node_id="bastet",
                    captured_at=now - timedelta(hours=30, minutes=index),
                    gpu_json=[],
                    cpu_json={},
                    memory_json={},
                    ollama_json={},
                    health_status="healthy",
                )
            )
        session.commit()

        summary = prune_snapshots(session, now=now, retention_hours=24, max_per_node=2, min_per_node=3)
        remaining = session.scalars(select(NodeSnapshot).order_by(NodeSnapshot.captured_at.desc())).all()

    assert summary.deleted_by_age == 2
    assert summary.deleted_by_count == 0
    assert len(remaining) == 3
    assert [snapshot.captured_at for snapshot in remaining] == [
        (now - timedelta(hours=30, minutes=index)).replace(tzinfo=None) for index in range(3)
    ]


def test_run_snapshot_pruning_uses_bootstrap_config_limits() -> None:
    session_factory = build_session_factory()
    now = datetime.now(UTC)

    with session_factory() as session:
        for index in range(4):
            session.add(
                NodeSnapshot(
                    node_id="bastet",
                    captured_at=now - timedelta(minutes=index),
                    gpu_json=[],
                    cpu_json={},
                    memory_json={},
                    ollama_json={},
                    health_status="healthy",
                )
            )
        session.commit()

    summary = run_snapshot_pruning(
        BootstrapConfig(snapshot_retention_hours=24, snapshot_max_per_node=2, snapshot_min_per_node=1),
        session_factory=session_factory,
    )

    with session_factory() as session:
        remaining = session.scalars(select(NodeSnapshot)).all()

    assert summary.deleted_by_count == 2
    assert len(remaining) == 2


def test_snapshot_pruning_worker_runs_until_stopped(monkeypatch) -> None:
    calls = []

    async def run_worker_once() -> None:
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()

        def fake_run_snapshot_pruning(config, session_factory):
            calls.append(config.snapshot_prune_interval_seconds)
            loop.call_soon_threadsafe(stop_event.set)
            return PruneSummary(deleted_by_age=1)

        monkeypatch.setattr("backend.app.workers.pruner.run_snapshot_pruning", fake_run_snapshot_pruning)
        await asyncio.wait_for(
            snapshot_pruning_worker(
                stop_event,
                BootstrapConfig(snapshot_prune_interval_seconds=60),
                session_factory=lambda: None,
            ),
            timeout=2,
        )

    asyncio.run(run_worker_once())

    assert calls == [60]
