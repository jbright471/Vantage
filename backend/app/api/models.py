from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException
import httpx
from pydantic import BaseModel

from backend.app.config import DEFAULT_BOOTSTRAP_CONFIG_PATH, load_bootstrap_config
from backend.app.db import SessionLocal
from backend.app.models import Node, Run
from backend.app.services.state import get_models_state

router = APIRouter()
CAPABILITY_CHECK_PROMPT = (
    "Reply with a compact JSON object describing the model health for this control-plane check. "
    'Use keys "mode", "json", and "notes". Return JSON only.'
)


class CapabilityCheckRequest(BaseModel):
    model_name: str
    node_id: str


def _coerce_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@router.get("/models")
def list_models() -> list[dict]:
    with SessionLocal() as session:
        return get_models_state(session)


def _run_local_capability_check(model_name: str, node_id: str) -> dict:
    config = load_bootstrap_config(DEFAULT_BOOTSTRAP_CONFIG_PATH)
    payload = {
        "model": model_name,
        "prompt": CAPABILITY_CHECK_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 96,
        },
    }
    started_at = datetime.now(UTC)
    errors: list[dict] = []

    for base_url in config.local_ollama_base_urls:
        try:
            response = httpx.post(f"{base_url}/api/generate", json=payload, timeout=45.0)
            response.raise_for_status()
            body = response.json()
            ended_at = datetime.now(UTC)
            return {
                "run_id": str(uuid4()),
                "source_type": "inference",
                "detail_type": "capability_check",
                "source_id": f"capability-check:{node_id}:{model_name}",
                "node_id": node_id,
                "model_name": model_name,
                "action_type": "infer",
                "status": "success",
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_ms": int((ended_at - started_at).total_seconds() * 1000),
                "summary": f"Capability check passed for {model_name} on {node_id}",
                "metadata_json": {
                    "base_url": base_url,
                    "prompt": CAPABILITY_CHECK_PROMPT,
                    "response_preview": body.get("response", "")[:240],
                },
            }
        except Exception as exc:
            errors.append({"base_url": base_url, "error": str(exc)})

    ended_at = datetime.now(UTC)
    return {
        "run_id": str(uuid4()),
        "source_type": "inference",
        "detail_type": "capability_check",
        "source_id": f"capability-check:{node_id}:{model_name}",
        "node_id": node_id,
        "model_name": model_name,
        "action_type": "infer",
        "status": "failed",
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_ms": int((ended_at - started_at).total_seconds() * 1000),
        "summary": f"Capability check failed for {model_name} on {node_id}",
        "metadata_json": {
            "prompt": CAPABILITY_CHECK_PROMPT,
            "errors": errors,
        },
    }


@router.post("/models/capability-check")
def run_capability_check(request: CapabilityCheckRequest) -> dict:
    with SessionLocal() as session:
        node = session.get(Node, request.node_id)
        if node is None:
            raise HTTPException(status_code=404, detail=f"Unknown node '{request.node_id}'")

    if node.role == "remote":
        started_at = datetime.now(UTC)
        try:
            response = httpx.post(
                f"{node.base_url}/capability-check",
                json={"model_name": request.model_name, "prompt": CAPABILITY_CHECK_PROMPT},
                timeout=60.0,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            ended_at = datetime.now(UTC)
            payload = {
                "run_id": str(uuid4()),
                "source_type": "inference",
                "detail_type": "capability_check",
                "source_id": f"capability-check:{request.node_id}:{request.model_name}",
                "node_id": request.node_id,
                "model_name": request.model_name,
                "action_type": "infer",
                "status": "failed",
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_ms": int((ended_at - started_at).total_seconds() * 1000),
                "summary": f"Capability check failed for {request.model_name} on {request.node_id}",
                "metadata_json": {
                    "prompt": CAPABILITY_CHECK_PROMPT,
                    "errors": [{"base_url": node.base_url, "error": str(exc)}],
                },
            }
    else:
        payload = _run_local_capability_check(request.model_name, request.node_id)

    payload["started_at"] = _coerce_datetime(payload.get("started_at")) or datetime.now(UTC)
    payload["ended_at"] = _coerce_datetime(payload.get("ended_at"))

    with SessionLocal() as session:
        existing = session.get(Run, payload["run_id"])
        if existing is None:
            session.add(
                Run(
                    run_id=payload["run_id"],
                    source_type=payload["source_type"],
                    detail_type=payload["detail_type"],
                    source_id=payload["source_id"],
                    node_id=payload["node_id"],
                    model_name=payload.get("model_name"),
                    action_type=payload.get("action_type"),
                    status=payload["status"],
                    started_at=payload["started_at"],
                    ended_at=payload.get("ended_at"),
                    duration_ms=payload.get("duration_ms"),
                    summary=payload["summary"],
                    metadata_json=payload.get("metadata_json", {}),
                )
            )
        else:
            existing.status = payload["status"]
            existing.ended_at = payload.get("ended_at")
            existing.duration_ms = payload.get("duration_ms")
            existing.summary = payload["summary"]
            existing.metadata_json = payload.get("metadata_json", {})
        session.commit()

    return payload
