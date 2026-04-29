from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from backend.app.db import SessionLocal
from backend.app.models import Run
from backend.app.services.reconciliation import acknowledge_warning_record
from backend.app.services.state import get_warnings_state
from backend.app.services.actions import build_action_run_payload

router = APIRouter()


@router.get("/warnings")
def list_warnings() -> list[dict]:
    with SessionLocal() as session:
        return get_warnings_state(session)


@router.patch("/warnings/{warning_id}/acknowledge")
def acknowledge_warning(warning_id: str) -> dict:
    with SessionLocal() as session:
        warning = acknowledge_warning_record(session, warning_id)
        if warning is None:
            raise HTTPException(status_code=404, detail=f"Unknown warning '{warning_id}'")

        payload = build_action_run_payload(
            node_id=warning.node_id or "control-plane",
            summary=f"Acknowledge warning {warning.warning_type}",
            source_id=f"acknowledge-warning:{warning.warning_id}",
            action_type="acknowledge-warning",
            metadata_json={
                "warning_id": warning.warning_id,
                "warning_type": warning.warning_type,
                "previous_status": "active",
                "new_status": warning.status,
            },
        )
        payload["status"] = "success"
        payload["ended_at"] = datetime.now(UTC)
        run = Run(**payload)
        session.add(run)
        session.commit()

        return {
            "warning_id": warning.warning_id,
            "warning_type": warning.warning_type,
            "severity": warning.severity,
            "node_id": warning.node_id,
            "status": warning.status,
            "summary": warning.summary,
            "run_id": run.run_id,
        }
