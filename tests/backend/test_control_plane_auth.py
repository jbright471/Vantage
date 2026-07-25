from fastapi.testclient import TestClient

from backend.app.main import app
from tests.backend.conftest import CONTROL_PLANE_TEST_TOKEN


def _unauthenticated_client() -> TestClient:
    return TestClient(app, headers={"Authorization": ""})


def test_control_plane_fails_closed_when_authentication_is_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("VANTAGE_CONTROL_PLANE_TOKEN", raising=False)
    monkeypatch.delenv("VANTAGE_SESSION_SIGNING_KEY", raising=False)

    with _unauthenticated_client() as client:
        protected = client.get("/api/nodes")
        readiness = client.get("/api/health/ready")

    assert protected.status_code == 503
    assert protected.json()["detail"] == "Control-plane authentication is not configured"
    assert readiness.status_code == 200


def test_control_plane_rejects_unauthenticated_requests() -> None:
    with _unauthenticated_client() as client:
        response = client.get("/api/nodes")

    assert response.status_code == 401
    assert response.json()["detail"] == "Control-plane authentication required"


def test_control_plane_accepts_operator_bearer_token() -> None:
    with _unauthenticated_client() as client:
        response = client.get(
            "/api/nodes",
            headers={"Authorization": f"Bearer {CONTROL_PLANE_TEST_TOKEN}"},
        )

    assert response.status_code == 200


def test_operator_login_establishes_http_only_session() -> None:
    with _unauthenticated_client() as client:
        login = client.post("/api/auth/login", json={"token": CONTROL_PLANE_TEST_TOKEN})
        status = client.get("/api/auth/status")
        protected = client.get("/api/nodes")

    assert login.status_code == 200
    assert login.json() == {"authenticated": True}
    assert "HttpOnly" in login.headers.get("set-cookie", "")
    assert status.json() == {"configured": True, "authenticated": True}
    assert protected.status_code == 200


def test_operator_session_requires_csrf_for_state_changes() -> None:
    with _unauthenticated_client() as client:
        assert client.post("/api/auth/login", json={"token": CONTROL_PLANE_TEST_TOKEN}).status_code == 200
        rejected = client.patch("/api/warnings/not-found/acknowledge")
        csrf_token = client.cookies.get("vantage_csrf")
        accepted_by_auth = client.patch(
            "/api/warnings/not-found/acknowledge",
            headers={"X-Vantage-CSRF": csrf_token or ""},
        )

    assert rejected.status_code == 403
    assert rejected.json()["detail"] == "CSRF validation failed"
    assert csrf_token
    assert accepted_by_auth.status_code == 404


def test_operator_login_rate_limits_repeated_failures() -> None:
    with _unauthenticated_client() as client:
        responses = [client.post("/api/auth/login", json={"token": "incorrect"}) for _ in range(6)]

    assert [response.status_code for response in responses[:5]] == [401] * 5
    assert responses[-1].status_code == 429
