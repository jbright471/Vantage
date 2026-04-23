from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.models import Base, NodeSnapshot
from backend.app.services.pruning import prune_snapshots


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
