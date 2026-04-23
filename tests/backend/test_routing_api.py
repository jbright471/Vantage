from fastapi.testclient import TestClient

from backend.app.main import app


def test_update_routing_rule_endpoint_reorders_nodes() -> None:
    with TestClient(app) as client:
        response = client.put(
            "/api/routing/interactive-default",
            json={"preferred_nodes": ["bastet", "jedi"]},
        )

    assert response.status_code == 200
    assert response.json()["preferred_nodes"] == ["bastet", "jedi"]
