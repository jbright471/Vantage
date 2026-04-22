from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from backend.app.config import DEFAULT_BOOTSTRAP_CONFIG_PATH, load_bootstrap_config
from backend.app.db import SessionLocal
from backend.app.models import Node, Run
from backend.app.services.actions import submit_refresh_node_action

router = APIRouter()


def _serialize_run(run: Run) -> dict:
    return {
        "run_id": run.run_id,
        "node_id": run.node_id,
        "status": run.status,
        "summary": run.summary,
        "started_at": run.started_at,
        "idempotency_key": run.idempotency_key,
    }


@router.post("/actions/refresh-node/{node_id}")
def refresh_node(node_id: str) -> dict:
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

    return {
        "run_id": payload["run_id"],
        "node_id": payload["node_id"],
        "status": payload["status"],
        "summary": payload["summary"],
        "started_at": payload["started_at"],
        "idempotency_key": payload["idempotency_key"],
    }
