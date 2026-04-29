from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.models import Base, WarningRecord
from backend.app.services.reconciliation import acknowledge_warning_record, detect_config_drift, upsert_warning_records


def test_detect_config_drift_flags_enabled_node_without_recent_snapshot() -> None:
    warnings = detect_config_drift(
        configured_nodes=[{"node_id": "bastet", "enabled": True}],
        observed_nodes={},
    )

    assert warnings[0]["warning_type"] == "config_drift"
    assert warnings[0]["node_id"] == "bastet"


def test_upsert_warning_records_reuses_existing_active_warning() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        warnings = detect_config_drift(
            configured_nodes=[{"node_id": "bastet", "enabled": True}],
            observed_nodes={},
        )
        upsert_warning_records(session, warnings)
        upsert_warning_records(session, warnings)

        persisted = session.scalars(select(WarningRecord)).all()

    assert len(persisted) == 1
    assert persisted[0].warning_type == "config_drift"


def test_acknowledged_warning_is_not_recreated_while_still_active() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        warnings = detect_config_drift(
            configured_nodes=[{"node_id": "bastet", "enabled": True}],
            observed_nodes={},
        )
        upsert_warning_records(session, warnings)
        warning = session.scalars(select(WarningRecord)).one()
        acknowledge_warning_record(session, warning.warning_id)
        upsert_warning_records(session, warnings)
        persisted = session.scalars(select(WarningRecord)).all()

    assert len(persisted) == 1
    assert persisted[0].status == "acknowledged"
