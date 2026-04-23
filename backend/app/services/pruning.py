from datetime import UTC, datetime, timedelta
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.models import NodeSnapshot


@dataclass(frozen=True)
class PruneSummary:
    deleted_by_age: int = 0
    deleted_by_count: int = 0

    @property
    def total_deleted(self) -> int:
        return self.deleted_by_age + self.deleted_by_count


def _timestamp(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _delete_snapshot_ids(session: Session, snapshot_ids: set[int]) -> int:
    if not snapshot_ids:
        return 0
    session.execute(delete(NodeSnapshot).where(NodeSnapshot.snapshot_id.in_(snapshot_ids)))
    return len(snapshot_ids)


def prune_snapshots(
    session: Session,
    now: datetime | None = None,
    retention_hours: int = 24,
    max_per_node: int = 5000,
    min_per_node: int = 1,
) -> PruneSummary:
    reference = now or datetime.now(UTC)
    cutoff = reference - timedelta(hours=retention_hours)
    snapshots = session.scalars(
        select(NodeSnapshot).order_by(NodeSnapshot.node_id, NodeSnapshot.captured_at.desc(), NodeSnapshot.snapshot_id.desc())
    ).all()
    snapshots_by_node: dict[str, list[NodeSnapshot]] = {}
    for snapshot in snapshots:
        snapshots_by_node.setdefault(snapshot.node_id, []).append(snapshot)

    delete_by_age: set[int] = set()
    delete_by_count: set[int] = set()
    for node_snapshots in snapshots_by_node.values():
        protected_ids = {
            snapshot.snapshot_id
            for snapshot in node_snapshots[: max(min_per_node, 0)]
            if snapshot.snapshot_id is not None
        }
        for snapshot in node_snapshots:
            if snapshot.snapshot_id in protected_ids:
                continue
            if _timestamp(snapshot.captured_at) < cutoff:
                delete_by_age.add(snapshot.snapshot_id)

        kept_after_age = [snapshot for snapshot in node_snapshots if snapshot.snapshot_id not in delete_by_age]
        for snapshot in kept_after_age[max(max_per_node, min_per_node) :]:
            if snapshot.snapshot_id not in protected_ids:
                delete_by_count.add(snapshot.snapshot_id)

    deleted_by_age = _delete_snapshot_ids(session, delete_by_age)
    deleted_by_count = _delete_snapshot_ids(session, delete_by_count - delete_by_age)
    session.commit()
    return PruneSummary(deleted_by_age=deleted_by_age, deleted_by_count=deleted_by_count)
