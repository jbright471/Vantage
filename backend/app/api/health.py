from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text

from backend.app.config import DEFAULT_BOOTSTRAP_CONFIG_PATH, load_bootstrap_config
from backend.app.db import SessionLocal, engine

router = APIRouter()

CONTROL_PLANE_SERVICE = "vantage-control-plane"
REQUIRED_TABLES = {
    "nodes",
    "node_snapshots",
    "runs",
    "model_placements",
    "routing_rules",
    "routing_rule_nodes",
    "warning_records",
}


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "app": "Vantage", "service": CONTROL_PLANE_SERVICE, "timestamp": _timestamp()}


@router.get("/health/live")
def liveness() -> dict:
    return {"status": "ok", "service": CONTROL_PLANE_SERVICE, "timestamp": _timestamp()}


@router.get("/health/ready")
def readiness() -> JSONResponse:
    checks = {
        "database": _check_database(),
        "schema": _check_schema(),
        "bootstrap_config": _check_bootstrap_config(),
    }
    is_ready = all(check["status"] == "ok" for check in checks.values())
    payload = {
        "status": "ok" if is_ready else "error",
        "service": CONTROL_PLANE_SERVICE,
        "timestamp": _timestamp(),
        "checks": checks,
    }
    return JSONResponse(status_code=200 if is_ready else 503, content=payload)


def _check_database() -> dict:
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1")).scalar_one()
    except Exception as exc:
        return {"status": "error", "detail": type(exc).__name__}
    return {"status": "ok"}


def _check_schema() -> dict:
    try:
        table_names = set(inspect(engine).get_table_names())
        missing_tables = sorted(REQUIRED_TABLES - table_names)
    except Exception as exc:
        return {"status": "error", "detail": type(exc).__name__}
    if missing_tables:
        return {"status": "error", "missing_tables": missing_tables}
    return {"status": "ok", "required_tables": sorted(REQUIRED_TABLES)}


def _check_bootstrap_config() -> dict:
    try:
        config = load_bootstrap_config(DEFAULT_BOOTSTRAP_CONFIG_PATH)
    except Exception as exc:
        return {"status": "error", "detail": type(exc).__name__}
    return {
        "status": "ok",
        "node_count": len(config.nodes),
        "poll_interval_seconds": config.poll_interval_seconds,
    }
