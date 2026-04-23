import asyncio
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
import logging
import os

from sqlalchemy import delete, select

from backend.app.collectors.local import collect_local_snapshot
from backend.app.collectors.remote import BastetClient
from backend.app.config import BootstrapConfig
from backend.app.db import SessionLocal
from backend.app.models import ModelPlacement, Node, NodeSnapshot
from backend.app.services.events import EventBroker
from backend.app.services.polling import classify_health, extract_model_placements, normalize_snapshot
from backend.app.services.pruning import prune_snapshots
from backend.app.services.reconciliation import detect_config_drift, resolve_warning_records, upsert_warning_records
from backend.app.services.state import build_full_state

logger = logging.getLogger("vantage.runtime")
BACKGROUND_POLLING_ENV = "VANTAGE_ENABLE_BACKGROUND_POLLING"


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


async def collect_remote_snapshot(node: Node) -> dict:
    client = BastetClient(node.base_url)
    captured_at = datetime.now(UTC)
    health_payload, gpu_payload, models_payload = await asyncio.gather(
        client.fetch_health(),
        client.fetch_gpu(),
        client.fetch_models(),
        return_exceptions=True,
    )

    errors: list[dict] = []
    results = (health_payload, gpu_payload, models_payload)
    if all(isinstance(result, Exception) for result in results):
        raise RuntimeError(f"Remote node '{node.node_id}' is unreachable")

    if isinstance(health_payload, Exception):
        errors.append({"source": "health", "error": str(health_payload)})
    elif health_payload.get("status") != "ok":
        errors.append({"source": "health", "error": f"status={health_payload.get('status', 'unknown')}"})

    if isinstance(gpu_payload, Exception):
        errors.append({"source": "gpu", "error": str(gpu_payload)})

    if isinstance(models_payload, Exception):
        errors.append({"source": "models", "error": str(models_payload)})

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
    }


async def collect_snapshot_for_node(node: Node, config: BootstrapConfig) -> dict:
    if node.role == "remote":
        return await collect_remote_snapshot(node)
    return await asyncio.to_thread(collect_local_snapshot, node.node_id, config.local_ollama_base_urls)


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
            continue

        with session_factory() as session:
            persisted_node = session.get(Node, node.node_id)
            if persisted_node is None:
                continue
            observed_nodes[node.node_id] = persist_node_observation(session, persisted_node, raw_snapshot)
            session.commit()

    with session_factory() as session:
        prune_snapshots(session, retention_hours=config.snapshot_retention_hours)
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
        state = build_full_state(session, config=config)

    if broker is not None:
        await broker.publish("full_state", state)

    return state


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
