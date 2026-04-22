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
