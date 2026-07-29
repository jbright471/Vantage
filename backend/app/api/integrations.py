from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.app.api.auth import require_external_api_token
from backend.app.collectors.registry import default_collector_registry
from backend.app.db import SessionLocal
from backend.app.services.integrations import (
    build_integration_events,
    build_integration_health,
    dispatch_email,
    dispatch_webhook,
    record_integration_dispatch,
    resolve_webhook_url,
)
from backend.app.services.reports import build_operator_markdown_report
from backend.app.services.router_import import import_router_runs

router = APIRouter()


class WebhookDispatchRequest(BaseModel):
    adapter: Literal["generic", "slack", "discord", "email"] = "generic"
    target_url: str | None = None
    include_warnings: bool = True
    include_failed_runs: bool = True
    include_eval_regressions: bool = True
    limit: int = Field(default=20, ge=1, le=100)


class RouterLogEntry(BaseModel):
    run_id: str | None = None
    source_id: str | None = None
    source: str | None = None
    node_id: str = "unknown"
    model_name: str | None = None
    status: str = "success"
    action_type: str = "route"
    started_at: str | None = None
    ended_at: str | None = None
    duration_ms: int | None = None
    summary: str = "Imported router request"
    metadata_json: dict = Field(default_factory=dict)


class RouterLogImportRequest(BaseModel):
    entries: list[RouterLogEntry] = Field(min_length=1, max_length=500)


@router.get("/integrations/events")
def list_integration_events(
    _: None = Depends(require_external_api_token),
    include_warnings: bool = True,
    include_failed_runs: bool = True,
    include_eval_regressions: bool = True,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    with SessionLocal() as session:
        events = build_integration_events(
            session,
            include_warnings=include_warnings,
            include_failed_runs=include_failed_runs,
            include_eval_regressions=include_eval_regressions,
            limit=limit,
        )
    return {
        "format": "vantage.integration.events.v1",
        "count": len(events),
        "events": events,
    }


@router.get("/integrations/health")
def get_integration_health() -> dict:
    with SessionLocal() as session:
        return build_integration_health(session)


@router.post("/integrations/webhooks/dispatch")
async def dispatch_integration_webhook(
    payload: WebhookDispatchRequest,
    _: None = Depends(require_external_api_token),
) -> dict:
    with SessionLocal() as session:
        events = build_integration_events(
            session,
            include_warnings=payload.include_warnings,
            include_failed_runs=payload.include_failed_runs,
            include_eval_regressions=payload.include_eval_regressions,
            limit=payload.limit,
        )
    try:
        if payload.adapter == "email":
            result = dispatch_email(events)
        else:
            target_url = resolve_webhook_url(payload.adapter, payload.target_url)
            if not target_url:
                raise HTTPException(status_code=400, detail="No webhook URL configured for requested adapter")
            result = await dispatch_webhook(payload.adapter, target_url, events)
        with SessionLocal() as session:
            return record_integration_dispatch(session, result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/integrations/import/router-runs", status_code=201)
def import_router_log_runs(payload: RouterLogImportRequest, _: None = Depends(require_external_api_token)) -> dict:
    with SessionLocal() as session:
        return import_router_runs(session, [entry.model_dump() for entry in payload.entries])


@router.get("/integrations/reports/operator.md")
def export_operator_report(
    title: str = "Vantage Operator Report",
    _: None = Depends(require_external_api_token),
) -> Response:
    with SessionLocal() as session:
        report = build_operator_markdown_report(session, title=title)
    return Response(
        content=report,
        media_type="text/markdown",
        headers={"Content-Disposition": 'attachment; filename="vantage-operator-report.md"'},
    )


@router.get("/integrations/collectors")
def list_collectors(_: None = Depends(require_external_api_token)) -> dict:
    collectors = default_collector_registry.list_collectors()
    return {"format": "vantage.collectors.v1", "count": len(collectors), "collectors": collectors}
