from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import Run


def _seed_run(run_id: str, *, status: str, node_id: str, started_at: datetime, detail_type: str = "agent_action") -> None:
    with SessionLocal() as session:
        session.merge(
            Run(
                run_id=run_id,
                source_type="agent_action",
                detail_type=detail_type,
                source_id=f"source:{run_id}",
                node_id=node_id,
                model_name=None,
                action_type="sync",
                status=status,
                started_at=started_at,
                ended_at=None,
                duration_ms=None,
                summary=f"Run {run_id}",
                metadata_json={"example": run_id},
            )
        )
        session.commit()


def test_runs_endpoint_filters_and_paginates_by_status() -> None:
    now = datetime.now(UTC)
    detail_type = "run_api_filter_test"
    with TestClient(app) as client:
        _seed_run("run-failed-1", status="failed", node_id="bastet", started_at=now, detail_type=detail_type)
        _seed_run(
            "run-success-1",
            status="success",
            node_id="jedi",
            started_at=now - timedelta(minutes=1),
            detail_type=detail_type,
        )
        _seed_run(
            "run-failed-2",
            status="failed",
            node_id="jedi",
            started_at=now - timedelta(minutes=2),
            detail_type=detail_type,
        )

        response = client.get(f"/api/runs?status=failed&detail_type={detail_type}&limit=1&offset=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["limit"] == 1
    assert payload["offset"] == 1
    assert [item["run_id"] for item in payload["items"]] == ["run-failed-2"]


def test_runs_export_json_preserves_metadata() -> None:
    now = datetime.now(UTC)
    detail_type = "run_api_json_export_test"
    with TestClient(app) as client:
        _seed_run("run-json-1", status="failed", node_id="bastet", started_at=now, detail_type=detail_type)

        response = client.get(f"/api/runs/export.json?status=failed&detail_type={detail_type}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["format"] == "json"
    assert payload["count"] >= 1
    assert any(run["run_id"] == "run-json-1" and run["metadata_json"]["example"] == "run-json-1" for run in payload["runs"])


def test_runs_export_csv_includes_operator_columns() -> None:
    now = datetime.now(UTC)
    detail_type = "run_api_csv_export_test"
    with TestClient(app) as client:
        _seed_run(
            "run-csv-1",
            status="submitted_unverified",
            node_id="bastet",
            started_at=now,
            detail_type=detail_type,
        )

        response = client.get(f"/api/runs/export.csv?status=submitted_unverified&detail_type={detail_type}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "run_id,status,node_id,summary" in response.text
    assert "run-csv-1,submitted_unverified,bastet,Run run-csv-1" in response.text
