from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.actions import build_action_run_payload, build_idempotency_key


def test_build_idempotency_key_is_stable_for_same_request() -> None:
    left = build_idempotency_key(
        action_type="restart-agent",
        target_node_id="bastet",
        target_resource_id="agent",
        payload={"service": "vantage-agent"},
        dedupe_window=30,
    )
    right = build_idempotency_key(
        action_type="restart-agent",
        target_node_id="bastet",
        target_resource_id="agent",
        payload={"service": "vantage-agent"},
        dedupe_window=30,
    )

    assert left == right


def test_build_action_run_payload_uses_submitted_unverified() -> None:
    payload = build_action_run_payload(node_id="bastet", summary="Refresh node bastet")

    assert payload["status"] == "submitted_unverified"
    assert payload["node_id"] == "bastet"


def test_refresh_node_action_endpoint_returns_submitted_unverified() -> None:
    with TestClient(app) as client:
        response = client.post("/api/actions/refresh-node/bastet")

    assert response.status_code == 200
    assert response.json()["status"] == "submitted_unverified"
    assert response.json()["node_id"] == "bastet"
