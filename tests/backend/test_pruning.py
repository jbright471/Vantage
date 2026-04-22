from datetime import UTC, datetime

from backend.app.services.pruning import prune_snapshots


class FakeSession:
    def __init__(self) -> None:
        self.cutoff = None

    def execute(self, statement) -> None:
        self.cutoff = statement

    def commit(self) -> None:
        pass


def test_prune_snapshots_uses_retention_cutoff() -> None:
    session = FakeSession()

    prune_snapshots(session, now=datetime.now(UTC), retention_hours=24)

    assert session.cutoff is not None
