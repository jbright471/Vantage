from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import WarningRecord


def detect_config_drift(configured_nodes: list[dict], observed_nodes: dict[str, dict]) -> list[dict]:
    warnings: list[dict] = []
    now = datetime.now(UTC)

    for node in configured_nodes:
        if node["enabled"] and node["node_id"] not in observed_nodes:
            warnings.append(
                {
                    "warning_id": str(uuid4()),
                    "warning_type": "config_drift",
                    "node_id": node["node_id"],
                    "severity": "warning",
                    "first_seen_at": now,
                    "last_seen_at": now,
                    "status": "active",
                    "summary": f"Configured node {node['node_id']} has no recent observation",
                    "metadata_json": {},
                }
            )

    return warnings


def upsert_warning_records(session: Session, warnings: list[dict]) -> None:
    for payload in warnings:
        existing = session.scalar(
            select(WarningRecord).where(
                WarningRecord.warning_type == payload["warning_type"],
                WarningRecord.node_id == payload["node_id"],
                WarningRecord.status == "active",
            )
        )
        if existing:
            existing.last_seen_at = payload["last_seen_at"]
            existing.summary = payload["summary"]
            existing.severity = payload["severity"]
            existing.metadata_json = payload["metadata_json"]
        else:
            session.add(WarningRecord(**payload))

    session.commit()


def resolve_warning_records(session: Session, warning_type: str, active_node_ids: set[str | None]) -> None:
    active_warnings = session.scalars(
        select(WarningRecord).where(
            WarningRecord.warning_type == warning_type,
            WarningRecord.status == "active",
        )
    ).all()
    now = datetime.now(UTC)

    for warning in active_warnings:
        if warning.node_id not in active_node_ids:
            warning.status = "resolved"
            warning.last_seen_at = now

    session.commit()
