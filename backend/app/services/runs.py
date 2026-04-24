from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from backend.app.models import Run


RUN_EXPORT_COLUMNS = [
    "run_id",
    "status",
    "node_id",
    "summary",
    "source_type",
    "detail_type",
    "model_name",
    "action_type",
    "started_at",
    "ended_at",
    "duration_ms",
    "metadata_json",
]


def serialize_run(run: Run) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "summary": run.summary,
        "status": run.status,
        "source_type": run.source_type,
        "detail_type": run.detail_type,
        "node_id": run.node_id,
        "started_at": run.started_at.isoformat(),
        "ended_at": run.ended_at.isoformat() if run.ended_at else None,
        "duration_ms": run.duration_ms,
        "model_name": run.model_name,
        "action_type": run.action_type,
        "metadata_json": run.metadata_json,
    }


def _filtered_runs_statement(
    *,
    status: str | None = None,
    node_id: str | None = None,
    detail_type: str | None = None,
) -> Select[tuple[Run]]:
    statement = select(Run)
    if status:
        statement = statement.where(Run.status == status)
    if node_id:
        statement = statement.where(Run.node_id == node_id)
    if detail_type:
        statement = statement.where(Run.detail_type == detail_type)
    return statement


def query_runs(
    session: Session,
    *,
    status: str | None = None,
    node_id: str | None = None,
    detail_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    bounded_limit = min(max(limit, 1), 500)
    bounded_offset = max(offset, 0)
    filtered = _filtered_runs_statement(status=status, node_id=node_id, detail_type=detail_type)
    total = session.scalar(select(func.count()).select_from(filtered.subquery())) or 0
    runs = session.scalars(filtered.order_by(Run.started_at.desc()).limit(bounded_limit).offset(bounded_offset)).all()
    return {
        "items": [serialize_run(run) for run in runs],
        "total": total,
        "limit": bounded_limit,
        "offset": bounded_offset,
        "filters": {
            "status": status,
            "node_id": node_id,
            "detail_type": detail_type,
        },
    }


def query_runs_for_export(
    session: Session,
    *,
    status: str | None = None,
    node_id: str | None = None,
    detail_type: str | None = None,
) -> list[dict[str, Any]]:
    filtered = _filtered_runs_statement(status=status, node_id=node_id, detail_type=detail_type)
    runs = session.scalars(filtered.order_by(Run.started_at.desc())).all()
    return [serialize_run(run) for run in runs]


def build_runs_json_export(runs: list[dict[str, Any]], filters: dict[str, str | None]) -> dict[str, Any]:
    return {
        "format": "json",
        "exported_at": datetime.now(UTC).isoformat(),
        "filters": filters,
        "count": len(runs),
        "runs": runs,
    }


def build_runs_csv_export(runs: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=RUN_EXPORT_COLUMNS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for run in runs:
        row = dict(run)
        row["metadata_json"] = json.dumps(run.get("metadata_json", {}), sort_keys=True)
        writer.writerow(row)
    return buffer.getvalue()
