from fastapi.testclient import TestClient

from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import WarningRecord


def test_acknowledge_warning_returns_404_for_unknown_warning() -> None:
    with TestClient(app) as client:
        response = client.patch("/api/warnings/missing-warning/acknowledge")

    assert response.status_code == 404


def test_acknowledge_warning_marks_warning_and_creates_run() -> None:
    with TestClient(app) as client:
        with SessionLocal() as session:
            session.add(
                WarningRecord(
                    warning_id="warning-to-ack",
                    warning_type="config_drift",
                    severity="warning",
                    node_id="bastet",
                    status="active",
                    summary="Configured node bastet has no recent observation",
                    metadata_json={},
                )
            )
            session.commit()

        response = client.patch("/api/warnings/warning-to-ack/acknowledge")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "acknowledged"
    assert payload["run_id"]
