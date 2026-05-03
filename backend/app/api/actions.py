from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from backend.app.config import DEFAULT_BOOTSTRAP_CONFIG_PATH, load_bootstrap_config
from backend.app.db import SessionLocal
from backend.app.models import Node, Run
from backend.app.services.actions import submit_refresh_node_action
from backend.app.services.runtime import run_single_node_poll

router = APIRouter()


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _serialize_run(run: Run) -> dict:
    return {
        "run_id": run.run_id,
        "node_id": run.node_id,
        "status": run.status,
        "summary": run.summary,
        "started_at": run.started_at,
        "ended_at": run.ended_at,
        "duration_ms": run.duration_ms,
        "idempotency_key": run.idempotency_key,
        "metadata_json": run.metadata_json,
    }


@router.post("/actions/refresh-node/{node_id}")
async def refresh_node(node_id: str) -> dict:
    config = load_bootstrap_config(DEFAULT_BOOTSTRAP_CONFIG_PATH)
    payload = submit_refresh_node_action(node_id, dedupe_window=config.idempotency_dedupe_seconds)
    cutoff = datetime.now(UTC) - timedelta(seconds=config.idempotency_dedupe_seconds)

    with SessionLocal() as session:
        node = session.get(Node, node_id)
        if node is None:
            raise HTTPException(status_code=404, detail=f"Unknown node '{node_id}'")

        existing = session.scalar(
            select(Run)
            .where(
                Run.idempotency_key == payload["idempotency_key"],
                Run.started_at >= cutoff,
            )
            .order_by(Run.started_at.desc())
        )
        if existing is not None:
            return _serialize_run(existing)

        run = Run(
            run_id=payload["run_id"],
            source_type=payload["source_type"],
            detail_type=payload["detail_type"],
            source_id=payload["source_id"],
            node_id=payload["node_id"],
            action_type=payload["action_type"],
            status=payload["status"],
            summary=payload["summary"],
            started_at=payload["started_at"],
            idempotency_key=payload["idempotency_key"],
            metadata_json=payload["metadata_json"],
        )
        session.add(run)
        session.commit()
        session.refresh(run)

    started_at = _as_utc(run.started_at)
    metadata_json = dict(run.metadata_json or {})
    try:
        observation = await run_single_node_poll(node_id, config)
        ended_at = datetime.now(UTC)
        run.status = "success"
        run.ended_at = ended_at
        run.duration_ms = int((ended_at - started_at).total_seconds() * 1000)
        run.summary = f"Refresh node {node_id} verified"
        run.metadata_json = {
            **metadata_json,
            "verified": True,
            **observation,
        }
    except Exception as exc:
        ended_at = datetime.now(UTC)
        run.status = "failed"
        run.ended_at = ended_at
        run.duration_ms = int((ended_at - started_at).total_seconds() * 1000)
        run.summary = f"Refresh node {node_id} failed verification"
        run.metadata_json = {
            **metadata_json,
            "verified": False,
            "errors": [{"error": str(exc)}],
        }

    with SessionLocal() as session:
        persisted_run = session.get(Run, run.run_id)
        if persisted_run is None:
            raise HTTPException(status_code=404, detail=f"Unknown action run '{run.run_id}'")
        persisted_run.status = run.status
        persisted_run.ended_at = run.ended_at
        persisted_run.duration_ms = run.duration_ms
        persisted_run.summary = run.summary
        persisted_run.metadata_json = run.metadata_json
        session.commit()
        session.refresh(persisted_run)
        return _serialize_run(persisted_run)
