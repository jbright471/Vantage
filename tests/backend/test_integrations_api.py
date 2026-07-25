import socket
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import Run, WarningRecord


EXTERNAL_TOKEN = "external-secret-token-0000000000000000"
EXTERNAL_HEADERS = {"X-Vantage-Api-Key": EXTERNAL_TOKEN}


def _configure_external_token(monkeypatch) -> None:
    monkeypatch.setenv("VANTAGE_EXTERNAL_API_TOKEN", EXTERNAL_TOKEN)


def _seed_integration_records() -> str:
    suffix = datetime.now(UTC).strftime("%H%M%S%f")
    with SessionLocal() as session:
        session.add(
            WarningRecord(
                warning_id=f"integration-warning-{suffix}",
                warning_type="config_drift",
                severity="warning",
                node_id="remote-worker",
                status="active",
                summary="Integration test warning",
                metadata_json={"source": "test"},
            )
        )
        session.add(
            Run(
                run_id=f"integration-failed-run-{suffix}",
                source_type="eval",
                detail_type="eval_attempt",
                source_id=f"integration:{suffix}",
                node_id="remote-worker",
                model_name="qwen:test",
                action_type="eval",
                status="failed",
                started_at=datetime.now(UTC),
                summary="Eval case failed for integration test",
                metadata_json={"score": {"passed": False, "reason": "expected_subset_mismatch"}},
            )
        )
        session.commit()
    return suffix


def test_integration_endpoints_require_external_token_when_configured(monkeypatch) -> None:
    _configure_external_token(monkeypatch)

    with TestClient(app) as client:
        unauthorized = client.get("/api/integrations/events")
        authorized = client.get("/api/integrations/events", headers=EXTERNAL_HEADERS)

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200


def test_integration_endpoints_fail_closed_without_external_token(monkeypatch) -> None:
    monkeypatch.delenv("VANTAGE_EXTERNAL_API_TOKEN", raising=False)

    with TestClient(app) as client:
        responses = [
            client.get("/api/integrations/events"),
            client.post("/api/integrations/webhooks/dispatch", json={"adapter": "generic"}),
            client.post("/api/integrations/import/router-runs", json={"entries": [{"node_id": "test"}]}),
            client.get("/api/integrations/reports/operator.md"),
            client.get("/api/integrations/collectors"),
        ]

    assert {response.status_code for response in responses} == {503}
    assert all(response.json()["detail"] == "External API authentication is not configured" for response in responses)


def test_integration_endpoints_fail_closed_with_weak_external_token(monkeypatch) -> None:
    monkeypatch.setenv("VANTAGE_EXTERNAL_API_TOKEN", "too-short")

    with TestClient(app) as client:
        response = client.get(
            "/api/integrations/events",
            headers={"X-Vantage-Api-Key": "too-short"},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "External API authentication is not configured"


def test_integration_events_include_warnings_failed_runs_and_eval_regressions(monkeypatch) -> None:
    _configure_external_token(monkeypatch)
    suffix = _seed_integration_records()

    with TestClient(app) as client:
        response = client.get("/api/integrations/events?limit=100", headers=EXTERNAL_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    event_types = {event["event_type"] for event in payload["events"]}
    event_ids = {event["event_id"] for event in payload["events"]}
    assert "warning" in event_types
    assert "failed_run" in event_types
    assert "eval_regression" in event_types
    assert f"warning:integration-warning-{suffix}" in event_ids
    assert f"run:integration-failed-run-{suffix}" in event_ids


def test_webhook_dispatch_posts_generic_payload(monkeypatch) -> None:
    _configure_external_token(monkeypatch)
    monkeypatch.setenv("VANTAGE_WEBHOOK_URL", "https://automation.example/vantage/secret?token=sensitive")
    monkeypatch.setenv("VANTAGE_WEBHOOK_ALLOWED_HOSTS", "automation.example")
    monkeypatch.setattr(
        "backend.app.services.integrations.socket.getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", 443)),
        ],
    )
    _seed_integration_records()
    captured = {}

    class FakeResponse:
        status_code = 202

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        def __init__(self, *, timeout: float, follow_redirects: bool) -> None:
            assert timeout == 10.0
            assert follow_redirects is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def post(self, url: str, *, json: dict) -> FakeResponse:
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("backend.app.services.integrations.httpx.AsyncClient", FakeAsyncClient)

    with TestClient(app) as client:
        response = client.post(
            "/api/integrations/webhooks/dispatch",
            json={"adapter": "generic", "limit": 5},
            headers=EXTERNAL_HEADERS,
        )

    assert response.status_code == 200
    assert captured["url"] == "https://automation.example/vantage/secret?token=sensitive"
    assert captured["json"]["format"] == "vantage.integration.events.v1"
    assert response.json()["status_code"] == 202
    assert response.json()["target_url"] == "https://automation.example/<redacted>"
    assert "sensitive" not in response.text


def test_webhook_dispatch_requires_an_explicit_host_allowlist(monkeypatch) -> None:
    _configure_external_token(monkeypatch)
    monkeypatch.setenv("VANTAGE_WEBHOOK_URL", "https://automation.example/vantage")
    monkeypatch.delenv("VANTAGE_WEBHOOK_ALLOWED_HOSTS", raising=False)

    with TestClient(app) as client:
        response = client.post(
            "/api/integrations/webhooks/dispatch",
            json={"adapter": "generic"},
            headers=EXTERNAL_HEADERS,
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "VANTAGE_WEBHOOK_ALLOWED_HOSTS must explicitly allow the webhook target"


def test_webhook_dispatch_rejects_private_dns_resolution(monkeypatch) -> None:
    _configure_external_token(monkeypatch)
    monkeypatch.setenv("VANTAGE_WEBHOOK_URL", "https://automation.example/vantage")
    monkeypatch.setenv("VANTAGE_WEBHOOK_ALLOWED_HOSTS", "automation.example")
    monkeypatch.setattr(
        "backend.app.services.integrations.socket.getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 443)),
        ],
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/integrations/webhooks/dispatch",
            json={"adapter": "generic"},
            headers=EXTERNAL_HEADERS,
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Webhook target resolves to a non-public address"


def test_webhook_dispatch_allows_explicit_rfc1918_opt_in(monkeypatch) -> None:
    _configure_external_token(monkeypatch)
    monkeypatch.setenv("VANTAGE_WEBHOOK_URL", "http://automation.internal/vantage")
    monkeypatch.setenv("VANTAGE_WEBHOOK_ALLOWED_HOSTS", "automation.internal")
    monkeypatch.setenv("VANTAGE_WEBHOOK_ALLOW_PRIVATE_NETWORKS", "1")
    monkeypatch.setattr(
        "backend.app.services.integrations.socket.getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("192.168.1.50", 80)),
        ],
    )

    class FakeResponse:
        status_code = 202

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        def __init__(self, *, timeout: float, follow_redirects: bool) -> None:
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def post(self, url: str, *, json: dict) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("backend.app.services.integrations.httpx.AsyncClient", FakeAsyncClient)

    with TestClient(app) as client:
        response = client.post(
            "/api/integrations/webhooks/dispatch",
            json={"adapter": "generic"},
            headers=EXTERNAL_HEADERS,
        )

    assert response.status_code == 200


def test_email_dispatch_records_last_dispatch(monkeypatch) -> None:
    _configure_external_token(monkeypatch)
    monkeypatch.setenv("VANTAGE_EMAIL_SMTP_HOST", "smtp.local")
    monkeypatch.setenv("VANTAGE_EMAIL_SMTP_PORT", "2525")
    monkeypatch.setenv("VANTAGE_EMAIL_FROM", "vantage@example.test")
    monkeypatch.setenv("VANTAGE_EMAIL_TO", "operator@example.test")
    monkeypatch.setenv("VANTAGE_EMAIL_USE_TLS", "0")
    _seed_integration_records()
    sent_messages = []

    class FakeSmtp:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            assert host == "smtp.local"
            assert port == 2525
            assert timeout == 10

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def starttls(self) -> None:
            raise AssertionError("TLS should be disabled")

        def send_message(self, message) -> None:
            sent_messages.append(message)

    monkeypatch.setattr("backend.app.services.integrations.smtplib.SMTP", FakeSmtp)

    with TestClient(app) as client:
        response = client.post(
            "/api/integrations/webhooks/dispatch",
            json={"adapter": "email", "limit": 5},
            headers=EXTERNAL_HEADERS,
        )
        health = client.get("/api/integrations/health")

    assert response.status_code == 200
    assert response.json()["adapter"] == "email"
    assert sent_messages
    assert health.json()["last_dispatch"]["adapter"] == "email"


def test_router_log_import_creates_durable_runs(monkeypatch) -> None:
    _configure_external_token(monkeypatch)
    run_id = f"router-import-{datetime.now(UTC).strftime('%H%M%S%f')}"
    payload = {
        "entries": [
            {
                "run_id": run_id,
                "node_id": "remote-worker",
                "model_name": "qwen:test",
                "status": "success",
                "summary": "Router selected remote-worker",
                "started_at": "2026-05-10T01:00:00Z",
                "metadata_json": {"priority_class": "interactive"},
            }
        ]
    }

    with TestClient(app) as client:
        first = client.post("/api/integrations/import/router-runs", json=payload, headers=EXTERNAL_HEADERS)
        second = client.post("/api/integrations/import/router-runs", json=payload, headers=EXTERNAL_HEADERS)

    assert first.status_code == 201
    assert first.json()["imported"] == 1
    assert second.json()["skipped"] == 1
    with SessionLocal() as session:
        run = session.get(Run, run_id)
    assert run is not None
    assert run.detail_type == "router_request"
    assert run.metadata_json["raw_router_log"]["metadata_json"]["priority_class"] == "interactive"


def test_operator_markdown_report_and_collectors_endpoint(monkeypatch) -> None:
    _configure_external_token(monkeypatch)

    with TestClient(app) as client:
        report = client.get("/api/integrations/reports/operator.md", headers=EXTERNAL_HEADERS)
        collectors = client.get("/api/integrations/collectors", headers=EXTERNAL_HEADERS)

    assert report.status_code == 200
    assert "# Vantage Operator Report" in report.text
    assert "## Fleet" in report.text
    assert collectors.status_code == 200
    collector = collectors.json()["collectors"][0]
    assert collector["name"] == "ollama"
    assert "models" in collector["capabilities"]
    assert "agent_hmac" in collector["auth_modes"]


def test_integration_health_exposes_security_counters(monkeypatch) -> None:
    monkeypatch.delenv("VANTAGE_EXTERNAL_API_TOKEN", raising=False)
    with SessionLocal() as session:
        from backend.app.services.security_events import increment_security_event_counter

        increment_security_event_counter(session, event_type="agent_auth_failed", node_id="remote-worker")

    with TestClient(app) as client:
        response = client.get("/api/integrations/health")

    assert response.status_code == 200
    counters = response.json()["security_event_counters"]
    assert any(counter["event_type"] == "agent_auth_failed" and counter["node_id"] == "remote-worker" for counter in counters)
