from fastapi.testclient import TestClient

from backend.app.main import app


def test_health_endpoint_remains_backward_compatible() -> None:
    with TestClient(app) as client:
        payload = client.get("/api/health").json()

    assert payload["status"] == "ok"
    assert payload["app"] == "Vantage"
    assert payload["service"] == "vantage-control-plane"
    assert "timestamp" in payload


def test_liveness_endpoint_reports_process_health() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health/live")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "vantage-control-plane"


def test_readiness_endpoint_checks_database_schema_and_config() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["database"]["status"] == "ok"
    assert payload["checks"]["schema"]["status"] == "ok"
    assert payload["checks"]["bootstrap_config"]["status"] == "ok"
    assert "nodes" in payload["checks"]["schema"]["required_tables"]
