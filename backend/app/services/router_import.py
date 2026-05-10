from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.models import Run


def _parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def import_router_runs(session: Session, entries: list[dict]) -> dict:
    imported = 0
    skipped = 0
    run_ids: list[str] = []

    for entry in entries:
        run_id = str(entry.get("run_id") or uuid4())
        if session.get(Run, run_id) is not None:
            skipped += 1
            continue

        started_at = _parse_timestamp(entry.get("started_at"))
        ended_at = _parse_timestamp(entry.get("ended_at")) if entry.get("ended_at") else None
        metadata_json = dict(entry.get("metadata_json") or {})
        metadata_json["imported_from"] = entry.get("source", "router_log")
        metadata_json["raw_router_log"] = entry

        run = Run(
            run_id=run_id,
            source_type="router",
            detail_type="router_request",
            source_id=str(entry.get("source_id") or f"router-import:{run_id}"),
            node_id=str(entry.get("node_id") or "unknown"),
            model_name=entry.get("model_name"),
            action_type=str(entry.get("action_type") or "route"),
            status=str(entry.get("status") or "success"),
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=entry.get("duration_ms"),
            summary=str(entry.get("summary") or "Imported router request"),
            metadata_json=metadata_json,
        )
        session.add(run)
        imported += 1
        run_ids.append(run_id)

    session.commit()
    return {"imported": imported, "skipped": skipped, "run_ids": run_ids}
