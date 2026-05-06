from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import EvalSchedule, ModelPlacement, Run, WarningRecord
from backend.app.services.eval_schedules import queue_due_eval_schedules
from backend.app.workers.eval_scheduler import run_due_eval_schedules


def test_create_eval_suite_and_case() -> None:
    with TestClient(app) as client:
        suite_response = client.post(
            "/api/evals/suites",
            json={"name": "Reasoning Smoke", "description": "Short-form reasoning prompts"},
        )

        assert suite_response.status_code == 201
        suite = suite_response.json()
        assert suite["name"] == "Reasoning Smoke"
        assert suite["case_count"] == 0

        case_response = client.post(
            f"/api/evals/suites/{suite['suite_id']}/cases",
            json={
                "name": "JSON Answer",
                "prompt": "Return a JSON object with an answer field.",
                "expected_json": {"shape": "answer"},
            },
        )

        assert case_response.status_code == 201
        updated_suite = case_response.json()
        assert updated_suite["case_count"] == 1
        assert updated_suite["cases"][0]["name"] == "JSON Answer"


def test_create_eval_case_returns_404_for_unknown_suite() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/evals/suites/missing-suite/cases",
            json={"name": "Missing", "prompt": "Hello", "expected_json": {}},
        )

    assert response.status_code == 404


def test_queue_eval_attempt_creates_run_records() -> None:
    model_name = "eval-test-model:latest"
    with TestClient(app) as client:
        suite_response = client.post(
            "/api/evals/suites",
            json={"name": "Routing Regression", "description": "Smoke test for queued eval attempts"},
        )
        suite = suite_response.json()
        client.post(
            f"/api/evals/suites/{suite['suite_id']}/cases",
            json={"name": "Case One", "prompt": "Return one.", "expected_json": {"answer": 1}},
        )
        client.post(
            f"/api/evals/suites/{suite['suite_id']}/cases",
            json={"name": "Case Two", "prompt": "Return two.", "expected_json": {"answer": 2}},
        )

        with SessionLocal() as session:
            session.add(
                ModelPlacement(
                    node_id="jedi",
                    model_name=model_name,
                    model_digest="sha256:test",
                    available=True,
                    last_seen_at=datetime.now(UTC),
                )
            )
            session.commit()

        response = client.post(
            f"/api/evals/suites/{suite['suite_id']}/attempts",
            json={"model_name": model_name, "node_id": "jedi"},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["suite_id"] == suite["suite_id"]
    assert payload["run_count"] == 2
    assert payload["runs"][0]["detail_type"] == "eval_attempt"
    assert payload["runs"][0]["status"] == "queued"
    assert payload["runs"][0]["metadata_json"]["attempt_id"] == payload["attempt_id"]


def test_queue_eval_attempt_requires_cases() -> None:
    model_name = "empty-eval-test-model:latest"
    with TestClient(app) as client:
        suite_response = client.post(
            "/api/evals/suites",
            json={"name": "Empty Suite", "description": "No cases yet"},
        )
        suite = suite_response.json()

        with SessionLocal() as session:
            session.add(
                ModelPlacement(
                    node_id="jedi",
                    model_name=model_name,
                    model_digest="sha256:empty",
                    available=True,
                    last_seen_at=datetime.now(UTC),
                )
            )
            session.commit()

        response = client.post(
            f"/api/evals/suites/{suite['suite_id']}/attempts",
            json={"model_name": model_name, "node_id": "jedi"},
        )

    assert response.status_code == 409


def test_execute_queued_eval_attempt_updates_run_with_score(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"response": '{"answer": 42, "notes": "ok"}'}

    model_name = "execute-eval-test-model:latest"
    monkeypatch.setattr("backend.app.services.evals.httpx.post", lambda *args, **kwargs: FakeResponse())

    with TestClient(app) as client:
        suite_response = client.post(
            "/api/evals/suites",
            json={"name": "Executable Suite", "description": "Executes one queued case"},
        )
        suite = suite_response.json()
        client.post(
            f"/api/evals/suites/{suite['suite_id']}/cases",
            json={"name": "Answer Case", "prompt": "Return answer 42 as JSON.", "expected_json": {"answer": 42}},
        )

        with SessionLocal() as session:
            session.add(
                ModelPlacement(
                    node_id="jedi",
                    model_name=model_name,
                    model_digest="sha256:execute",
                    available=True,
                    last_seen_at=datetime.now(UTC),
                )
            )
            session.commit()

        queue_response = client.post(
            f"/api/evals/suites/{suite['suite_id']}/attempts",
            json={"model_name": model_name, "node_id": "jedi"},
        )
        run_id = queue_response.json()["runs"][0]["run_id"]

        response = client.post(f"/api/evals/runs/{run_id}/execute")

    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "success"
    assert run["metadata_json"]["score"]["passed"] is True
    assert run["metadata_json"]["response_json"]["answer"] == 42


def test_score_history_endpoint_returns_eval_aggregates(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"response": '{"answer": 42}'}

    model_name = "history-eval-test-model:latest"
    monkeypatch.setattr("backend.app.services.evals.httpx.post", lambda *args, **kwargs: FakeResponse())

    with TestClient(app) as client:
        suite_response = client.post(
            "/api/evals/suites",
            json={"name": "History Suite", "description": "History aggregation"},
        )
        suite = suite_response.json()
        client.post(
            f"/api/evals/suites/{suite['suite_id']}/cases",
            json={"name": "Answer Case", "prompt": "Return answer 42 as JSON.", "expected_json": {"answer": 42}},
        )

        with SessionLocal() as session:
            session.add(
                ModelPlacement(
                    node_id="jedi",
                    model_name=model_name,
                    model_digest="sha256:history",
                    available=True,
                    last_seen_at=datetime.now(UTC),
                )
            )
            session.commit()

        queue_response = client.post(
            f"/api/evals/suites/{suite['suite_id']}/attempts",
            json={"model_name": model_name, "node_id": "jedi"},
        )
        run_id = queue_response.json()["runs"][0]["run_id"]
        client.post(f"/api/evals/runs/{run_id}/execute")

        response = client.get("/api/evals/score-history")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_runs"] >= 1
    assert any(placement["model_name"] == model_name for placement in payload["placements"])


def test_create_eval_schedule_and_list_it() -> None:
    model_name = "schedule-api-test-model:latest"
    with TestClient(app) as client:
        suite_response = client.post(
            "/api/evals/suites",
            json={"name": "Scheduled Suite", "description": "Runs on an interval"},
        )
        suite = suite_response.json()
        client.post(
            f"/api/evals/suites/{suite['suite_id']}/cases",
            json={"name": "Scheduled Case", "prompt": "Return JSON.", "expected_json": {"ok": True}},
        )

        with SessionLocal() as session:
            session.add(
                ModelPlacement(
                    node_id="jedi",
                    model_name=model_name,
                    model_digest="sha256:schedule-api",
                    available=True,
                    last_seen_at=datetime.now(UTC),
                )
            )
            session.commit()

        create_response = client.post(
            "/api/evals/schedules",
            json={
                "suite_id": suite["suite_id"],
                "model_name": model_name,
                "node_id": "jedi",
                "interval_minutes": 30,
                "enabled": True,
                "auto_execute": True,
            },
        )
        list_response = client.get("/api/evals/schedules")

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["suite_id"] == suite["suite_id"]
    assert created["suite_name"] == "Scheduled Suite"
    assert created["model_name"] == model_name
    assert created["node_id"] == "jedi"
    assert created["interval_minutes"] == 30
    assert created["enabled"] is True
    assert created["auto_execute"] is True
    assert created["next_run_at"] is not None
    assert list_response.status_code == 200
    assert any(schedule["schedule_id"] == created["schedule_id"] for schedule in list_response.json())


def test_queue_eval_schedule_now_creates_runs_without_advancing_next_run() -> None:
    model_name = "schedule-queue-now-test-model:latest"
    with TestClient(app) as client:
        suite_response = client.post(
            "/api/evals/suites",
            json={"name": "Queue Now Suite", "description": "Manual schedule queueing"},
        )
        suite = suite_response.json()
        client.post(
            f"/api/evals/suites/{suite['suite_id']}/cases",
            json={"name": "Queue Now Case", "prompt": "Return JSON.", "expected_json": {"ok": True}},
        )

        with SessionLocal() as session:
            session.add(
                ModelPlacement(
                    node_id="jedi",
                    model_name=model_name,
                    model_digest="sha256:queue-now",
                    available=True,
                    last_seen_at=datetime.now(UTC),
                )
            )
            session.commit()

        create_response = client.post(
            "/api/evals/schedules",
            json={
                "suite_id": suite["suite_id"],
                "model_name": model_name,
                "node_id": "jedi",
                "interval_minutes": 30,
                "enabled": True,
                "auto_execute": False,
            },
        )
        schedule = create_response.json()
        response = client.post(f"/api/evals/schedules/{schedule['schedule_id']}/queue-now")

    assert response.status_code == 201
    payload = response.json()
    assert payload["run_count"] == 1
    assert payload["schedule"]["next_run_at"] == schedule["next_run_at"]
    assert payload["schedule"]["last_queued_at"] is not None
    assert payload["runs"][0]["metadata_json"]["trigger"] == "schedule_manual"
    assert payload["runs"][0]["metadata_json"]["schedule_id"] == schedule["schedule_id"]


def test_queue_eval_schedule_now_rejects_disabled_schedule() -> None:
    model_name = "schedule-disabled-queue-now-test-model:latest"
    with TestClient(app) as client:
        suite_response = client.post(
            "/api/evals/suites",
            json={"name": "Disabled Queue Now Suite", "description": "Disabled schedule queueing"},
        )
        suite = suite_response.json()
        client.post(
            f"/api/evals/suites/{suite['suite_id']}/cases",
            json={"name": "Disabled Case", "prompt": "Return JSON.", "expected_json": {"ok": True}},
        )

        with SessionLocal() as session:
            session.add(
                ModelPlacement(
                    node_id="jedi",
                    model_name=model_name,
                    model_digest="sha256:queue-now-disabled",
                    available=True,
                    last_seen_at=datetime.now(UTC),
                )
            )
            session.commit()

        create_response = client.post(
            "/api/evals/schedules",
            json={
                "suite_id": suite["suite_id"],
                "model_name": model_name,
                "node_id": "jedi",
                "interval_minutes": 30,
                "enabled": False,
                "auto_execute": False,
            },
        )
        schedule = create_response.json()
        response = client.post(f"/api/evals/schedules/{schedule['schedule_id']}/queue-now")

    assert response.status_code == 409
    assert "disabled" in response.json()["detail"].lower()


def test_due_eval_schedule_queues_runs_and_advances_next_run() -> None:
    model_name = "schedule-service-test-model:latest"
    now = datetime.now(UTC)

    with TestClient(app) as client:
        suite_response = client.post(
            "/api/evals/suites",
            json={"name": "Due Schedule Suite", "description": "Due schedule service"},
        )
        suite = suite_response.json()
        client.post(
            f"/api/evals/suites/{suite['suite_id']}/cases",
            json={"name": "Due Case", "prompt": "Return JSON.", "expected_json": {"ok": True}},
        )

    with SessionLocal() as session:
        session.add(
            ModelPlacement(
                node_id="jedi",
                model_name=model_name,
                model_digest="sha256:schedule-service",
                available=True,
                last_seen_at=now,
            )
        )
        schedule = EvalSchedule(
            schedule_id="schedule-service-test",
            suite_id=suite["suite_id"],
            model_name=model_name,
            node_id="jedi",
            interval_minutes=15,
            enabled=True,
            created_at=now - timedelta(minutes=30),
            updated_at=now - timedelta(minutes=30),
            next_run_at=now - timedelta(minutes=1),
            metadata_json={},
        )
        session.add(schedule)
        session.commit()

        summary = queue_due_eval_schedules(session, now=now)
        queued = session.scalars(
            select(Run).where(
                Run.detail_type == "eval_attempt",
                Run.metadata_json["schedule_id"].as_string() == "schedule-service-test",
            )
        ).all()
        refreshed_schedule = session.get(EvalSchedule, "schedule-service-test")

    assert summary["schedules_checked"] >= 1
    assert summary["schedules_queued"] == 1
    assert summary["runs_queued"] == 1
    assert len(queued) == 1
    assert queued[0].status == "queued"
    assert queued[0].metadata_json["trigger"] == "schedule"
    assert refreshed_schedule is not None
    assert refreshed_schedule.last_queued_at == now.replace(tzinfo=None)
    assert refreshed_schedule.next_run_at == (now + timedelta(minutes=15)).replace(tzinfo=None)


def test_due_auto_execute_eval_schedule_runs_and_scores(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"response": '{"ok": true}'}

    model_name = "schedule-auto-exec-test-model:latest"
    now = datetime.now(UTC)
    monkeypatch.setattr("backend.app.services.evals.httpx.post", lambda *args, **kwargs: FakeResponse())

    with TestClient(app) as client:
        suite_response = client.post(
            "/api/evals/suites",
            json={"name": "Auto Execute Suite", "description": "Runs automatically"},
        )
        suite = suite_response.json()
        client.post(
            f"/api/evals/suites/{suite['suite_id']}/cases",
            json={"name": "Auto Case", "prompt": "Return ok true.", "expected_json": {"ok": True}},
        )

    with SessionLocal() as session:
        session.add(
            ModelPlacement(
                node_id="jedi",
                model_name=model_name,
                model_digest="sha256:schedule-auto-exec",
                available=True,
                last_seen_at=now,
            )
        )
        session.add(
            EvalSchedule(
                schedule_id="schedule-auto-exec-test",
                suite_id=suite["suite_id"],
                model_name=model_name,
                node_id="jedi",
                interval_minutes=15,
                enabled=True,
                auto_execute=True,
                created_at=now - timedelta(minutes=30),
                updated_at=now - timedelta(minutes=30),
                next_run_at=now - timedelta(minutes=1),
                metadata_json={},
            )
        )
        session.commit()

    summary = run_due_eval_schedules(app.state.config)

    with SessionLocal() as session:
        run = session.scalar(
            select(Run).where(
                Run.detail_type == "eval_attempt",
                Run.metadata_json["schedule_id"].as_string() == "schedule-auto-exec-test",
            )
        )
        refreshed_schedule = session.get(EvalSchedule, "schedule-auto-exec-test")

    assert summary["schedules_queued"] == 1
    assert summary["runs_queued"] == 1
    assert summary["runs_executed"] == 1
    assert run is not None
    assert run.status == "success"
    assert run.metadata_json["score"]["passed"] is True
    assert refreshed_schedule is not None
    assert refreshed_schedule.metadata_json["last_auto_execute"]["runs_executed"] == 1


def test_failed_auto_execute_eval_schedule_creates_warning(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"response": '{"ok": false}'}

    model_name = "schedule-warning-test-model:latest"
    now = datetime.now(UTC)
    monkeypatch.setattr("backend.app.services.evals.httpx.post", lambda *args, **kwargs: FakeResponse())

    with TestClient(app) as client:
        suite_response = client.post(
            "/api/evals/suites",
            json={"name": "Warning Suite", "description": "Creates schedule warning"},
        )
        suite = suite_response.json()
        client.post(
            f"/api/evals/suites/{suite['suite_id']}/cases",
            json={"name": "Warning Case", "prompt": "Return ok true.", "expected_json": {"ok": True}},
        )

    with SessionLocal() as session:
        session.add(
            ModelPlacement(
                node_id="jedi",
                model_name=model_name,
                model_digest="sha256:schedule-warning",
                available=True,
                last_seen_at=now,
            )
        )
        session.add(
            EvalSchedule(
                schedule_id="schedule-warning-test",
                suite_id=suite["suite_id"],
                model_name=model_name,
                node_id="jedi",
                interval_minutes=15,
                enabled=True,
                auto_execute=True,
                created_at=now - timedelta(minutes=30),
                updated_at=now - timedelta(minutes=30),
                next_run_at=now - timedelta(minutes=1),
                metadata_json={},
            )
        )
        session.commit()

    summary = run_due_eval_schedules(app.state.config)

    with SessionLocal() as session:
        warning = session.get(WarningRecord, "eval-schedule-failure:schedule-warning-test")

    assert summary["runs_executed"] == 1
    assert summary["runs_failed"] == 1
    assert warning is not None
    assert warning.status == "active"
    assert warning.warning_type == "eval_schedule_failure"
    assert warning.node_id == "jedi"
    assert warning.metadata_json["schedule_id"] == "schedule-warning-test"
    assert warning.metadata_json["failed_count"] == 1


def test_clean_auto_execute_eval_schedule_resolves_existing_warning(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"response": '{"ok": true}'}

    model_name = "schedule-warning-resolve-test-model:latest"
    now = datetime.now(UTC)
    monkeypatch.setattr("backend.app.services.evals.httpx.post", lambda *args, **kwargs: FakeResponse())

    with TestClient(app) as client:
        suite_response = client.post(
            "/api/evals/suites",
            json={"name": "Warning Resolve Suite", "description": "Resolves schedule warning"},
        )
        suite = suite_response.json()
        client.post(
            f"/api/evals/suites/{suite['suite_id']}/cases",
            json={"name": "Resolve Case", "prompt": "Return ok true.", "expected_json": {"ok": True}},
        )

    with SessionLocal() as session:
        session.add(
            ModelPlacement(
                node_id="jedi",
                model_name=model_name,
                model_digest="sha256:schedule-warning-resolve",
                available=True,
                last_seen_at=now,
            )
        )
        session.add(
            EvalSchedule(
                schedule_id="schedule-warning-resolve-test",
                suite_id=suite["suite_id"],
                model_name=model_name,
                node_id="jedi",
                interval_minutes=15,
                enabled=True,
                auto_execute=True,
                created_at=now - timedelta(minutes=30),
                updated_at=now - timedelta(minutes=30),
                next_run_at=now - timedelta(minutes=1),
                metadata_json={},
            )
        )
        session.add(
            WarningRecord(
                warning_id="eval-schedule-failure:schedule-warning-resolve-test",
                warning_type="eval_schedule_failure",
                severity="warning",
                node_id="jedi",
                first_seen_at=now - timedelta(minutes=20),
                last_seen_at=now - timedelta(minutes=20),
                status="active",
                summary="Previous eval schedule failure",
                metadata_json={"schedule_id": "schedule-warning-resolve-test"},
            )
        )
        session.commit()

    summary = run_due_eval_schedules(app.state.config)

    with SessionLocal() as session:
        warning = session.get(WarningRecord, "eval-schedule-failure:schedule-warning-resolve-test")

    assert summary["runs_executed"] == 1
    assert summary["runs_failed"] == 0
    assert warning is not None
    assert warning.status == "resolved"
