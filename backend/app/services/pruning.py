from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from backend.app.models import NodeSnapshot


def prune_snapshots(session, now: datetime | None = None, retention_hours: int = 24) -> None:
    reference = now or datetime.now(UTC)
    cutoff = reference - timedelta(hours=retention_hours)
    session.execute(delete(NodeSnapshot).where(NodeSnapshot.captured_at < cutoff))
    session.commit()
