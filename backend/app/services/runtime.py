import asyncio
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
import logging
import os

from sqlalchemy import delete, select

from backend.app.collectors.local import collect_local_snapshot
from backend.app.collectors.remote import AgentAuthenticationError, RemoteAgentClient
from backend.app.config import BootstrapConfig
from backend.app.db import SessionLocal
from backend.app.models import ModelPlacement, Node, NodeSnapshot, Run, WarningRecord
from backend.app.services.endpoint_overrides import filter_enabled_local_ollama_endpoints
from backend.app.services.events import EventBroker
from backend.app.services.polling import classify_health, extract_model_placements, normalize_snapshot
from backend.app.services.reconciliation import detect_config_drift, resolve_warning_records, upsert_warning_records
from backend.app.services.security_events import increment_security_event_counter
from backend.app.services.state import build_full_state

logger = logging.getLogger("vantage.runtime")
BACKGROUND_POLLING_ENV = "VANTAGE_ENABLE_BACKGROUND_POLLING"
AGENT_AUTH_MODE_ENV = "VANTAGE_AGENT_AUTH_MODE"
AGENT_KEY_ID_ENV = "VANTAGE_AGENT_KEY_ID"


def background_polling_enabled() -> bool:
    configured = os.getenv(BACKGROUND_POLLING_ENV)
    if configured is not None:
        return configured.lower() not in {"0", "false", "no"}
    return "PYTEST_CURRENT_TEST" not in os.environ


def _timestamp(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _serialize_remote_models(payload: dict) -> list[dict]:
    return [
        {
            "name": model["model_name"],
            "digest": model.get("model_digest"),
        }
        for model in payload.get("models", [])
        if model.get("model_name")
    ]


def resolve_agent_auth_token(config: BootstrapConfig) -> str | None:
    token = os.getenv(config.agent_auth_token_env)
    return token if token else None


def resolve_agent_auth_mode(node: Node) -> str:
    if node.auth_mode:
        return node.auth_mode
    configured = os.getenv(AGENT_AUTH_MODE_ENV)
    return configured if configured else "bearer"


def resolve_agent_key_id(node: Node) -> str | None:
    if node.auth_config_json and node.auth_config_json.get("key_id"):
        return str(node.auth_config_json["key_id"])
    configured = os.getenv(AGENT_KEY_ID_ENV)
    return configured if configured else None


def build_agent_auth_warning(node_id: str, error: Exception) -> dict:
    now = datetime.now(UTC)
    return {
        "warning_id": f"agent-auth-failed:{node_id}",
        "warning_type": "agent_auth_failed",
        "node_id": node_id,
        "severity": "critical",
        "first_seen_at": now,
        "last_seen_at": now,
        "status": "active",
        "summary": f"Remote agent authentication failed for {node_id}",
        "metadata_json": {
            "error": str(error),
            "category": "security",
            "recommended_action": "Verify the configured agent token, auth mode, key id, and token rotation state.",
        },
    }


async def collect_remote_snapshot(node: Node, auth_token: str | None = None) -> dict:
    client = RemoteAgentClient(
        node.base_url,
        auth_token=auth_token,
        auth_mode=resolve_agent_auth_mode(node),
        key_id=resolve_agent_key_id(node),
    )
    captured_at = datetime.now(UTC)
    health_payload, gpu_payload, models_payload, runs_payload = await asyncio.gather(
        client.fetch_health(),
        client.fetch_gpu(),
        client.fetch_models(),
        client.fetch_runs(),
        return_exceptions=True,
    )

    errors: list[dict] = []
    results = (health_payload, gpu_payload, models_payload)
    if all(isinstance(result, Exception) for result in results):
        auth_error = next((result for result in results if isinstance(result, AgentAuthenticationError)), None)
        if auth_error is not None:
            raise auth_error
        raise RuntimeError(f"Remote node '{node.node_id}' is unreachable")

    if isinstance(health_payload, Exception):
        errors.append({"source": "health", "error": str(health_payload)})
    elif health_payload.get("status") != "ok":
        errors.append({"source": "health", "error": f"status={health_payload.get('status', 'unknown')}"})

    if isinstance(gpu_payload, Exception):
        errors.append({"source": "gpu", "error": str(gpu_payload)})

    if isinstance(models_payload, Exception):
        errors.append({"source": "models", "error": str(models_payload)})

    if isinstance(runs_payload, Exception):
        errors.append({"source": "runs", "error": str(runs_payload)})

    return {
        "node_id": node.node_id,
        "captured_at": captured_at,
        "gpu_json": [] if isinstance(gpu_payload, Exception) else gpu_payload.get("gpus", []),
        "cpu_json": {},
        "memory_json": {},
        "ollama_json": {
            "status": "error" if errors else "ok",
            "base_urls": [node.base_url],
            "models": [] if isinstance(models_payload, Exception) else _serialize_remote_models(models_payload),
            "errors": errors,
        },
        "runs_json": [] if isinstance(runs_payload, Exception) else runs_payload.get("runs", []),
    }


async def collect_snapshot_for_node(node: Node, config: BootstrapConfig) -> dict:
    if node.role == "remote":
        return await collect_remote_snapshot(node, auth_token=resolve_agent_auth_token(config))
    with SessionLocal() as session:
        enabled_urls = filter_enabled_local_ollama_endpoints(session, config.local_ollama_base_urls)
    return await asyncio.to_thread(collect_local_snapshot, node.node_id, enabled_urls)


def persist_node_observation(session, node: Node, raw_snapshot: dict) -> dict:
    normalized = normalize_snapshot(raw_snapshot)
    captured_at = _timestamp(normalized["captured_at"])
    health_status = classify_health(normalized)

    session.add(
        NodeSnapshot(
            node_id=node.node_id,
            captured_at=captured_at,
            gpu_json=normalized["gpu_json"],
            cpu_json=normalized["cpu_json"],
            memory_json=normalized["memory_json"],
            ollama_json=normalized["ollama_json"],
            health_status=health_status,
        )
    )

    node.last_seen_at = captured_at

    if normalized["ollama_json"].get("status") == "ok":
        session.execute(delete(ModelPlacement).where(ModelPlacement.node_id == node.node_id))
        for placement in extract_model_placements(node.node_id, normalized["ollama_json"]):
            session.add(
                ModelPlacement(
                    node_id=placement["node_id"],
                    model_name=placement["model_name"],
                    model_digest=placement["model_digest"],
                    available=placement["available"],
                    last_seen_at=captured_at,
                )
            )

    return normalized


def _coerce_remote_datetime(value, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        return _timestamp(value)
    if isinstance(value, str):
        return _timestamp(datetime.fromisoformat(value.replace("Z", "+00:00")))
    return fallback


def persist_remote_runs(session, node_id: str, payloads: list[dict], observed_at: datetime) -> None:
    active_loaded_model_run_ids: set[str] = set()

    for payload in payloads:
        run_id = payload.get("run_id")
        if not run_id:
            continue

        started_at = _coerce_remote_datetime(payload.get("started_at"), observed_at)
        ended_at = payload.get("ended_at")
        coerced_ended_at = _coerce_remote_datetime(ended_at, observed_at) if ended_at else None

        existing = session.get(Run, run_id)
        if existing is None:
            session.add(
                Run(
                    run_id=run_id,
                    source_type=payload.get("source_type", "remote_agent"),
                    detail_type=payload.get("detail_type", "remote_activity"),
                    source_id=payload.get("source_id", f"remote:{node_id}:{run_id}"),
                    node_id=payload.get("node_id", node_id),
                    model_name=payload.get("model_name"),
                    action_type=payload.get("action_type"),
                    status=payload.get("status", "running"),
                    started_at=started_at,
                    ended_at=coerced_ended_at,
                    duration_ms=payload.get("duration_ms"),
                    summary=payload.get("summary", f"Remote activity on {node_id}"),
                    metadata_json=payload.get("metadata_json", {}),
                )
            )
        else:
            existing.source_type = payload.get("source_type", existing.source_type)
            existing.detail_type = payload.get("detail_type", existing.detail_type)
            existing.source_id = payload.get("source_id", existing.source_id)
            existing.node_id = payload.get("node_id", existing.node_id)
            existing.model_name = payload.get("model_name")
            existing.action_type = payload.get("action_type")
            existing.status = payload.get("status", existing.status)
            existing.ended_at = coerced_ended_at
            existing.duration_ms = payload.get("duration_ms")
            existing.summary = payload.get("summary", existing.summary)
            existing.metadata_json = payload.get("metadata_json", {})

        if payload.get("detail_type") == "ollama_loaded_model" and payload.get("status") == "running":
            active_loaded_model_run_ids.add(run_id)

    existing_active_runs = session.scalars(
        select(Run).where(
            Run.node_id == node_id,
            Run.detail_type == "ollama_loaded_model",
            Run.status == "running",
        )
    ).all()
    for run in existing_active_runs:
        if run.run_id in active_loaded_model_run_ids:
            continue
        run.status = "success"
        run.ended_at = observed_at
        if run.duration_ms is None:
            run.duration_ms = int((observed_at - _timestamp(run.started_at)).total_seconds() * 1000)
        metadata_json = dict(run.metadata_json)
        metadata_json["released_at"] = observed_at.isoformat()
        run.metadata_json = metadata_json


async def run_poll_cycle(
    config: BootstrapConfig,
    broker: EventBroker | None = None,
    session_factory: Callable = SessionLocal,
) -> dict:
    with session_factory() as session:
        nodes = session.scalars(select(Node).where(Node.enabled.is_(True)).order_by(Node.display_name)).all()

    observed_nodes: dict[str, dict] = {}

    for node in nodes:
        try:
            raw_snapshot = await collect_snapshot_for_node(node, config)
        except Exception as exc:
            logger.warning("collector_failed node=%s error=%s", node.node_id, exc)
            if isinstance(exc, AgentAuthenticationError):
                with session_factory() as session:
                    increment_security_event_counter(session, event_type="agent_auth_failed", node_id=node.node_id)
                    upsert_warning_records(session, [build_agent_auth_warning(node.node_id, exc)])
            continue

        with session_factory() as session:
            persisted_node = session.get(Node, node.node_id)
            if persisted_node is None:
                continue
            observed_nodes[node.node_id] = persist_node_observation(session, persisted_node, raw_snapshot)
            if persisted_node.role == "remote":
                persist_remote_runs(
                    session,
                    persisted_node.node_id,
                    raw_snapshot.get("runs_json", []),
                    _timestamp(raw_snapshot.get("captured_at", datetime.now(UTC))),
                )
            session.commit()

    with session_factory() as session:
        warnings = detect_config_drift(
            configured_nodes=[{"node_id": node.node_id, "enabled": node.enabled} for node in nodes],
            observed_nodes=observed_nodes,
        )
        upsert_warning_records(session, warnings)
        resolve_warning_records(
            session,
            warning_type="config_drift",
            active_node_ids={warning["node_id"] for warning in warnings},
        )
        resolve_warning_records(
            session,
            warning_type="agent_auth_failed",
            active_node_ids={node_id for node_id in {node.node_id for node in nodes} if node_id not in observed_nodes},
        )
        state = build_full_state(session, config=config)

    if broker is not None:
        await broker.publish("full_state", state)

    return state


async def run_single_node_poll(
    node_id: str,
    config: BootstrapConfig,
    session_factory: Callable = SessionLocal,
) -> dict:
    with session_factory() as session:
        node = session.get(Node, node_id)
        if node is None:
            raise ValueError(f"Unknown node '{node_id}'")
        if not node.enabled:
            raise ValueError(f"Node '{node_id}' is disabled")

    raw_snapshot = await collect_snapshot_for_node(node, config)

    with session_factory() as session:
        persisted_node = session.get(Node, node_id)
        if persisted_node is None:
            raise ValueError(f"Unknown node '{node_id}'")
        normalized = persist_node_observation(session, persisted_node, raw_snapshot)
        if persisted_node.role == "remote":
            persist_remote_runs(
                session,
                persisted_node.node_id,
                raw_snapshot.get("runs_json", []),
                _timestamp(raw_snapshot.get("captured_at", datetime.now(UTC))),
            )

        active_drift = session.scalars(
            select(WarningRecord).where(
                WarningRecord.warning_type.in_(("config_drift", "agent_auth_failed")),
                WarningRecord.node_id == node_id,
                WarningRecord.status.in_(("active", "acknowledged")),
            )
        ).all()
        for warning in active_drift:
            warning.status = "resolved"
            warning.last_seen_at = datetime.now(UTC)

        session.commit()
        return {
            "node_id": node_id,
            "captured_at": _timestamp(normalized["captured_at"]).isoformat(),
            "observed_status": classify_health(normalized),
            "ollama_status": normalized["ollama_json"].get("status"),
            "model_count": len(normalized["ollama_json"].get("models", [])),
            "error_count": len(normalized["ollama_json"].get("errors", [])),
        }


async def poll_forever(
    stop_event: asyncio.Event,
    config: BootstrapConfig,
    broker: EventBroker,
    session_factory: Callable = SessionLocal,
) -> None:
    while not stop_event.is_set():
        try:
            await run_poll_cycle(config, broker=broker, session_factory=session_factory)
        except Exception:
            logger.exception("poll_cycle_failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=config.poll_interval_seconds)
        except asyncio.TimeoutError:
            continue


async def stop_polling_task(task: asyncio.Task[None]) -> None:
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
