import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4


def build_idempotency_key(
    action_type: str,
    target_node_id: str,
    target_resource_id: str,
    payload: dict,
    dedupe_window: int,
) -> str:
    stable = json.dumps(
        {
            "action_type": action_type,
            "target_node_id": target_node_id,
            "target_resource_id": target_resource_id,
            "payload": payload,
            "dedupe_window": dedupe_window,
        },
        sort_keys=True,
    )
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def build_action_run_payload(
    node_id: str,
    summary: str,
    *,
    idempotency_key: str | None = None,
    source_id: str | None = None,
    action_type: str = "sync",
    metadata_json: dict | None = None,
) -> dict:
    return {
        "run_id": str(uuid4()),
        "source_type": "agent_action",
        "detail_type": "agent_action",
        "source_id": source_id or f"action:{node_id}",
        "node_id": node_id,
        "action_type": action_type,
        "status": "submitted_unverified",
        "summary": summary,
        "started_at": datetime.now(UTC),
        "idempotency_key": idempotency_key,
        "metadata_json": metadata_json or {},
    }


def submit_refresh_node_action(node_id: str, *, dedupe_window: int) -> dict:
    idempotency_key = build_idempotency_key(
        action_type="refresh-node",
        target_node_id=node_id,
        target_resource_id="node",
        payload={"node_id": node_id},
        dedupe_window=dedupe_window,
    )
    return build_action_run_payload(
        node_id=node_id,
        summary=f"Refresh node {node_id}",
        source_id=f"refresh-node:{node_id}",
        action_type="sync",
        idempotency_key=idempotency_key,
        metadata_json={"requested_action": "refresh-node"},
    )


def submit_set_node_enabled_action(node_id: str, *, enabled: bool, dedupe_window: int) -> dict:
    requested_action = "re-enable-node" if enabled else "quarantine-node"
    idempotency_key = build_idempotency_key(
        action_type="set-node-enabled",
        target_node_id=node_id,
        target_resource_id="node",
        payload={"node_id": node_id, "enabled": enabled},
        dedupe_window=dedupe_window,
    )
    return build_action_run_payload(
        node_id=node_id,
        summary=f"{'Re-enable' if enabled else 'Quarantine'} node {node_id}",
        source_id=f"set-node-enabled:{node_id}:{str(enabled).lower()}",
        action_type="set-node-enabled",
        idempotency_key=idempotency_key,
        metadata_json={"requested_action": requested_action, "requested_enabled": enabled},
    )


def submit_set_local_ollama_endpoint_disabled_action(
    node_id: str,
    *,
    endpoint_url: str,
    disabled: bool,
    dedupe_window: int,
) -> dict:
    requested_action = "disable-local-ollama-endpoint" if disabled else "re-enable-local-ollama-endpoint"
    idempotency_key = build_idempotency_key(
        action_type="set-local-ollama-endpoint-disabled",
        target_node_id=node_id,
        target_resource_id=endpoint_url,
        payload={"node_id": node_id, "endpoint_url": endpoint_url, "disabled": disabled},
        dedupe_window=dedupe_window,
    )
    return build_action_run_payload(
        node_id=node_id,
        summary=f"{'Disable' if disabled else 'Re-enable'} local Ollama endpoint {endpoint_url}",
        source_id=f"set-local-ollama-endpoint-disabled:{node_id}:{endpoint_url}:{str(disabled).lower()}",
        action_type="set-local-ollama-endpoint-disabled",
        idempotency_key=idempotency_key,
        metadata_json={
            "requested_action": requested_action,
            "endpoint_url": endpoint_url,
            "requested_disabled": disabled,
        },
    )
