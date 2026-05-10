from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from backend.app.db import SessionLocal
from backend.app.services.audit import AUDIT_SIGNING_KEY_ENV, build_signed_audit_bundle, resolve_audit_signing_key
from backend.app.services.runs import build_runs_csv_export, build_runs_json_export, query_runs, query_runs_for_export

router = APIRouter()


@router.get("/runs")
def list_runs(
    status: str | None = None,
    node_id: str | None = None,
    detail_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    with SessionLocal() as session:
        return query_runs(
            session,
            status=status,
            node_id=node_id,
            detail_type=detail_type,
            limit=limit,
            offset=offset,
        )


@router.get("/runs/export.json")
def export_runs_json(
    status: str | None = None,
    node_id: str | None = None,
    detail_type: str | None = None,
) -> dict:
    filters = {"status": status, "node_id": node_id, "detail_type": detail_type}
    with SessionLocal() as session:
        runs = query_runs_for_export(session, **filters)
    return build_runs_json_export(runs, filters)


@router.get("/runs/export.csv")
def export_runs_csv(
    status: str | None = None,
    node_id: str | None = None,
    detail_type: str | None = None,
) -> Response:
    with SessionLocal() as session:
        runs = query_runs_for_export(session, status=status, node_id=node_id, detail_type=detail_type)
    return Response(
        content=build_runs_csv_export(runs),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="vantage-runs.csv"'},
    )


@router.get("/runs/export.bundle.json")
def export_runs_audit_bundle(
    status: str | None = None,
    node_id: str | None = None,
    detail_type: str | None = None,
) -> dict:
    signing_key = resolve_audit_signing_key()
    if signing_key is None:
        raise HTTPException(
            status_code=503,
            detail=f"Signed audit export requires {AUDIT_SIGNING_KEY_ENV} to be configured",
        )

    filters = {"status": status, "node_id": node_id, "detail_type": detail_type}
    with SessionLocal() as session:
        runs = query_runs_for_export(session, **filters)
    return build_signed_audit_bundle(runs, filters, signing_key=signing_key)
