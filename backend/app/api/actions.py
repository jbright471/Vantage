from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select

from backend.app.config import DEFAULT_BOOTSTRAP_CONFIG_PATH, load_bootstrap_config
from backend.app.db import SessionLocal
from backend.app.models import AppSetting, Node, RoutingRuleNode, Run
from backend.app.services.actions import (
    submit_refresh_node_action,
    submit_set_local_ollama_endpoint_disabled_action,
    submit_set_node_enabled_action,
)
from backend.app.services.bootstrap import NODE_ENABLED_OVERRIDES_KEY, get_node_enabled_overrides
from backend.app.services.endpoint_overrides import (
    filter_enabled_local_ollama_endpoints,
    normalize_endpoint_url,
    resolve_local_ollama_base_urls,
    set_local_ollama_endpoint_disabled,
)
from backend.app.services.runtime import run_single_node_poll

router = APIRouter()


class NodeEnabledRequest(BaseModel):
    enabled: bool


class LocalOllamaEndpointRequest(BaseModel):
    endpoint_url: str
    disabled: bool


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


def _set_node_enabled_override(session, node_id: str, enabled: bool) -> None:
    overrides = get_node_enabled_overrides(session)
    overrides[node_id] = enabled
    setting = session.get(AppSetting, NODE_ENABLED_OVERRIDES_KEY)
    value_json = {"nodes": overrides}
    if setting is None:
        session.add(AppSetting(key=NODE_ENABLED_OVERRIDES_KEY, value_json=value_json, updated_at=datetime.now(UTC)))
    else:
        setting.value_json = value_json
        setting.updated_at = datetime.now(UTC)


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


@router.patch("/actions/nodes/{node_id}/enabled")
def set_node_enabled(node_id: str, payload: NodeEnabledRequest) -> dict:
    config = load_bootstrap_config(DEFAULT_BOOTSTRAP_CONFIG_PATH)
    action_payload = submit_set_node_enabled_action(
        node_id,
        enabled=payload.enabled,
        dedupe_window=config.idempotency_dedupe_seconds,
    )
    started_at = _as_utc(action_payload["started_at"])
    ended_at = datetime.now(UTC)

    with SessionLocal() as session:
        node = session.get(Node, node_id)
        if node is None:
            raise HTTPException(status_code=404, detail=f"Unknown node '{node_id}'")

        if not payload.enabled and node.enabled:
            enabled_node_ids = session.scalars(select(Node.node_id).where(Node.enabled.is_(True))).all()
            if len(enabled_node_ids) <= 1:
                raise HTTPException(status_code=400, detail="Cannot quarantine the last enabled node")

        previous_enabled = node.enabled
        removed_from_rules: list[str] = []
        if previous_enabled != payload.enabled:
            node.enabled = payload.enabled
            _set_node_enabled_override(session, node_id, payload.enabled)
            if not payload.enabled:
                route_nodes = session.scalars(
                    select(RoutingRuleNode).where(RoutingRuleNode.node_id == node_id)
                ).all()
                removed_from_rules = sorted({route_node.rule_id for route_node in route_nodes})
                session.execute(delete(RoutingRuleNode).where(RoutingRuleNode.node_id == node_id))

        metadata_json = {
            **action_payload["metadata_json"],
            "previous_enabled": previous_enabled,
            "requested_enabled": payload.enabled,
            "changed": previous_enabled != payload.enabled,
            "removed_from_routing_rules": removed_from_rules,
        }
        run = Run(
            run_id=action_payload["run_id"],
            source_type=action_payload["source_type"],
            detail_type=action_payload["detail_type"],
            source_id=action_payload["source_id"],
            node_id=action_payload["node_id"],
            action_type=action_payload["action_type"],
            status="success",
            summary=action_payload["summary"] + (" applied" if previous_enabled != payload.enabled else " already current"),
            started_at=action_payload["started_at"],
            ended_at=ended_at,
            duration_ms=int((ended_at - started_at).total_seconds() * 1000),
            idempotency_key=action_payload["idempotency_key"],
            metadata_json=metadata_json,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return _serialize_run(run)


@router.patch("/actions/nodes/{node_id}/local-ollama-endpoint")
def set_local_ollama_endpoint(node_id: str, payload: LocalOllamaEndpointRequest) -> dict:
    config = load_bootstrap_config(DEFAULT_BOOTSTRAP_CONFIG_PATH)
    endpoint_url = normalize_endpoint_url(payload.endpoint_url)
    configured_urls = set(resolve_local_ollama_base_urls(config.local_ollama_base_urls))
    if endpoint_url not in configured_urls:
        raise HTTPException(status_code=400, detail="Endpoint is not a configured local Ollama base URL")

    action_payload = submit_set_local_ollama_endpoint_disabled_action(
        node_id,
        endpoint_url=endpoint_url,
        disabled=payload.disabled,
        dedupe_window=config.idempotency_dedupe_seconds,
    )
    started_at = _as_utc(action_payload["started_at"])
    ended_at = datetime.now(UTC)

    with SessionLocal() as session:
        node = session.get(Node, node_id)
        if node is None:
            raise HTTPException(status_code=404, detail=f"Unknown node '{node_id}'")
        if node.role == "remote":
            raise HTTPException(status_code=400, detail="Remote node Ollama endpoints must be managed by the remote agent")

        enabled_urls = filter_enabled_local_ollama_endpoints(session, config.local_ollama_base_urls)
        if payload.disabled and endpoint_url in enabled_urls and len(enabled_urls) <= 1:
            raise HTTPException(status_code=400, detail="Cannot disable the last enabled local Ollama endpoint")

        override_result = set_local_ollama_endpoint_disabled(session, endpoint_url, payload.disabled)
        metadata_json = {
            **action_payload["metadata_json"],
            **override_result,
        }
        run = Run(
            run_id=action_payload["run_id"],
            source_type=action_payload["source_type"],
            detail_type=action_payload["detail_type"],
            source_id=action_payload["source_id"],
            node_id=action_payload["node_id"],
            action_type=action_payload["action_type"],
            status="success",
            summary=action_payload["summary"] + (" applied" if override_result["changed"] else " already current"),
            started_at=action_payload["started_at"],
            ended_at=ended_at,
            duration_ms=int((ended_at - started_at).total_seconds() * 1000),
            idempotency_key=action_payload["idempotency_key"],
            metadata_json=metadata_json,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return _serialize_run(run)
