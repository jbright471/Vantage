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
        assert updated_suite["cases"][0]["score_type"] == "json_subset"


def test_eval_intelligence_presets_are_managed_settings() -> None:
    preset_payload = {
        "name": "Managed flaky review",
        "controls": {
            "window_days": "14",
            "placement_key": "qwen:test::bastet",
            "flakiness_min_rate": "0.35",
            "failure_cluster_min_count": "3",
        },
    }
    with TestClient(app) as client:
        created = client.put("/api/evals/intelligence-presets", json=preset_payload)
        listed = client.get("/api/evals/intelligence-presets")
        deleted = client.delete(f"/api/evals/intelligence-presets/{created.json()['id']}")

    assert created.status_code == 200
    assert created.json()["name"] == "Managed flaky review"
    assert created.json()["storage"] == "managed"
    assert listed.status_code == 200
    assert any(preset["name"] == "Managed flaky review" for preset in listed.json()["presets"])
    assert deleted.status_code == 200


def test_update_and_duplicate_eval_suite_and_case() -> None:
    with TestClient(app) as client:
        suite_response = client.post(
            "/api/evals/suites",
            json={"name": "Editable Suite", "description": "Before"},
        )
        suite = suite_response.json()
        case_response = client.post(
            f"/api/evals/suites/{suite['suite_id']}/cases",
            json={
                "name": "Editable Case",
                "prompt": "Return old.",
                "expected_json": {"old": True},
                "score_type": "json_subset",
                "score_config_json": {},
            },
        )
        case = case_response.json()["cases"][0]

        updated_suite_response = client.patch(
            f"/api/evals/suites/{suite['suite_id']}",
            json={"name": "Edited Suite", "description": "After"},
        )
        updated_case_response = client.patch(
            f"/api/evals/suites/{suite['suite_id']}/cases/{case['case_id']}",
            json={
                "name": "Edited Case",
                "prompt": "Return ticket-123.",
                "expected_json": {},
                "score_type": "regex",
                "score_config_json": {"pattern": r"ticket-\d+"},
                "sort_order": 7,
            },
        )
        duplicate_case_response = client.post(
            f"/api/evals/suites/{suite['suite_id']}/cases/{case['case_id']}/duplicate"
        )
        duplicate_response = client.post(f"/api/evals/suites/{suite['suite_id']}/duplicate")

    assert updated_suite_response.status_code == 200
    assert updated_suite_response.json()["name"] == "Edited Suite"
    assert updated_case_response.status_code == 200
    edited_case = updated_case_response.json()["cases"][0]
    assert edited_case["name"] == "Edited Case"
    assert edited_case["score_type"] == "regex"
    assert edited_case["score_config_json"]["pattern"] == r"ticket-\d+"
    assert edited_case["sort_order"] == 7
    assert duplicate_case_response.status_code == 201
    duplicate_case_suite = duplicate_case_response.json()
    assert duplicate_case_suite["case_count"] == 2
    assert any(item["name"].endswith("Copy") for item in duplicate_case_suite["cases"])
    assert duplicate_response.status_code == 201
    duplicate = duplicate_response.json()
    assert duplicate["suite_id"] != suite["suite_id"]
    assert duplicate["name"].startswith("Edited Suite")
    assert duplicate["case_count"] == 2
    assert duplicate["cases"][0]["score_type"] == "regex"


def test_create_eval_case_returns_404_for_unknown_suite() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/evals/suites/missing-suite/cases",
            json={"name": "Missing", "prompt": "Hello", "expected_json": {}},
        )

    assert response.status_code == 404


def test_delete_eval_case_returns_updated_suite_payload() -> None:
    with TestClient(app) as client:
        suite_response = client.post(
            "/api/evals/suites",
            json={"name": "Delete Case Suite", "description": "Case cleanup"},
        )
        suite = suite_response.json()
        case_response = client.post(
            f"/api/evals/suites/{suite['suite_id']}/cases",
            json={"name": "Temporary Case", "prompt": "Return JSON.", "expected_json": {"ok": True}},
        )
        case = case_response.json()["cases"][0]

        response = client.delete(f"/api/evals/suites/{suite['suite_id']}/cases/{case['case_id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["suite_id"] == suite["suite_id"]
    assert payload["case_count"] == 0
    assert payload["cases"] == []


def test_delete_eval_schedule_removes_schedule() -> None:
    model_name = "schedule-delete-test-model:latest"
    with TestClient(app) as client:
        suite_response = client.post(
            "/api/evals/suites",
            json={"name": "Delete Schedule Suite", "description": "Schedule cleanup"},
        )
        suite = suite_response.json()
        client.post(
            f"/api/evals/suites/{suite['suite_id']}/cases",
            json={"name": "Delete Schedule Case", "prompt": "Return JSON.", "expected_json": {"ok": True}},
        )

        with SessionLocal() as session:
            session.add(
                ModelPlacement(
                    node_id="jedi",
                    model_name=model_name,
                    model_digest="sha256:delete-schedule",
                    available=True,
                    last_seen_at=datetime.now(UTC),
                )
            )
            session.commit()

        schedule_response = client.post(
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
        schedule = schedule_response.json()

        response = client.delete(f"/api/evals/schedules/{schedule['schedule_id']}")
        list_response = client.get("/api/evals/schedules")

    assert response.status_code == 204
    assert all(item["schedule_id"] != schedule["schedule_id"] for item in list_response.json())


def test_delete_eval_suite_requires_no_cases_or_schedules() -> None:
    with TestClient(app) as client:
        suite_response = client.post(
            "/api/evals/suites",
            json={"name": "Protected Suite", "description": "Must delete cases first"},
        )
        suite = suite_response.json()
        client.post(
            f"/api/evals/suites/{suite['suite_id']}/cases",
            json={"name": "Protected Case", "prompt": "Return JSON.", "expected_json": {"ok": True}},
        )

        response = client.delete(f"/api/evals/suites/{suite['suite_id']}")

    assert response.status_code == 409
    assert "cases" in response.json()["detail"].lower()


def test_delete_empty_eval_suite_removes_suite() -> None:
    with TestClient(app) as client:
        suite_response = client.post(
            "/api/evals/suites",
            json={"name": "Empty Delete Suite", "description": "Safe suite cleanup"},
        )
        suite = suite_response.json()

        response = client.delete(f"/api/evals/suites/{suite['suite_id']}")
        list_response = client.get("/api/evals/suites")

    assert response.status_code == 204
    assert all(item["suite_id"] != suite["suite_id"] for item in list_response.json())


def test_export_and_import_eval_suite() -> None:
    with TestClient(app) as client:
        suite_response = client.post(
            "/api/evals/suites",
            json={"name": "Portable Suite", "description": "Can be moved"},
        )
        suite = suite_response.json()
        client.post(
            f"/api/evals/suites/{suite['suite_id']}/cases",
            json={
                "name": "Portable Case",
                "prompt": "Say portable.",
                "expected_json": {},
                "score_type": "contains",
                "score_config_json": {"expected_text": "portable"},
            },
        )

        export_response = client.get(f"/api/evals/suites/{suite['suite_id']}/export")
        exported = export_response.json()
        exported["name"] = "Imported Portable Suite"
        import_response = client.post("/api/evals/suites/import", json=exported)

    assert export_response.status_code == 200
    assert exported["cases"][0]["score_type"] == "contains"
    assert import_response.status_code == 201
    imported = import_response.json()
    assert imported["name"] == "Imported Portable Suite"
    assert imported["case_count"] == 1
    assert imported["cases"][0]["score_config_json"]["expected_text"] == "portable"


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
    assert payload["runs"][0]["metadata_json"]["model_digest"] == "sha256:test"


def test_execute_eval_attempt_batch_runs_all_queued_cases(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"response": '{"answer": 1}'}

    model_name = "batch-execute-eval-test-model:latest"
    monkeypatch.setattr("backend.app.services.evals.httpx.post", lambda *args, **kwargs: FakeResponse())

    with TestClient(app) as client:
        suite_response = client.post(
            "/api/evals/suites",
            json={"name": "Batch Execute Suite", "description": "Executes queued attempt"},
        )
        suite = suite_response.json()
        for index in [1, 2]:
            client.post(
                f"/api/evals/suites/{suite['suite_id']}/cases",
                json={"name": f"Batch Case {index}", "prompt": "Return answer 1.", "expected_json": {"answer": 1}},
            )

        with SessionLocal() as session:
            session.add(
                ModelPlacement(
                    node_id="jedi",
                    model_name=model_name,
                    model_digest="sha256:batch-execute",
                    available=True,
                    last_seen_at=datetime.now(UTC),
                )
            )
            session.commit()

        queue_response = client.post(
            f"/api/evals/suites/{suite['suite_id']}/attempts",
            json={"model_name": model_name, "node_id": "jedi"},
        )
        attempt_id = queue_response.json()["attempt_id"]
        execute_response = client.post(f"/api/evals/attempts/{attempt_id}/execute")

    assert execute_response.status_code == 200
    payload = execute_response.json()
    assert payload["attempt_id"] == attempt_id
    assert payload["runs_executed"] == 2
    assert all(run["status"] == "success" for run in payload["runs"])


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


def test_score_history_filters_window_placement_and_thresholds() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    with SessionLocal() as session:
        session.add_all(
            [
                Run(
                    run_id="eval-filter-run-1",
                    source_type="eval",
                    detail_type="eval_attempt",
                    source_id="eval-suite:filter-suite:case:filter-case",
                    node_id="jedi",
                    model_name="filter-model-a:latest",
                    action_type="eval",
                    status="failed",
                    started_at=now - timedelta(days=1),
                    duration_ms=100,
                    summary="Failed filtered eval",
                    metadata_json={
                        "suite_id": "filter-suite",
                        "suite_name": "Filter Suite",
                        "case_id": "filter-case",
                        "case_name": "Filter Case",
                        "score_type": "json_subset",
                        "score": {
                            "passed": False,
                            "score": 0,
                            "reason": "expected_subset_mismatch",
                            "missing_or_mismatched": ["answer"],
                        },
                    },
                ),
                Run(
                    run_id="eval-filter-run-2",
                    source_type="eval",
                    detail_type="eval_attempt",
                    source_id="eval-suite:filter-suite:case:filter-case",
                    node_id="jedi",
                    model_name="filter-model-a:latest",
                    action_type="eval",
                    status="success",
                    started_at=now - timedelta(days=2),
                    duration_ms=100,
                    summary="Passed filtered eval",
                    metadata_json={
                        "suite_id": "filter-suite",
                        "suite_name": "Filter Suite",
                        "case_id": "filter-case",
                        "case_name": "Filter Case",
                        "score_type": "json_subset",
                        "score": {"passed": True, "score": 1, "reason": "expected_subset_matched"},
                    },
                ),
                Run(
                    run_id="eval-filter-run-other-model",
                    source_type="eval",
                    detail_type="eval_attempt",
                    source_id="eval-suite:filter-suite:case:filter-case",
                    node_id="bastet",
                    model_name="filter-model-b:latest",
                    action_type="eval",
                    status="failed",
                    started_at=now - timedelta(days=1),
                    duration_ms=100,
                    summary="Other placement eval",
                    metadata_json={
                        "suite_id": "filter-suite",
                        "suite_name": "Filter Suite",
                        "case_id": "filter-case",
                        "case_name": "Filter Case",
                        "score_type": "json_subset",
                        "score": {
                            "passed": False,
                            "score": 0,
                            "reason": "expected_subset_mismatch",
                            "missing_or_mismatched": ["answer"],
                        },
                    },
                ),
                Run(
                    run_id="eval-filter-run-old",
                    source_type="eval",
                    detail_type="eval_attempt",
                    source_id="eval-suite:filter-suite:case:old-case",
                    node_id="jedi",
                    model_name="filter-model-a:latest",
                    action_type="eval",
                    status="failed",
                    started_at=now - timedelta(days=90),
                    duration_ms=100,
                    summary="Old filtered eval",
                    metadata_json={
                        "suite_id": "filter-suite",
                        "suite_name": "Filter Suite",
                        "case_id": "old-case",
                        "case_name": "Old Case",
                        "score_type": "json_subset",
                        "score": {
                            "passed": False,
                            "score": 0,
                            "reason": "old_failure",
                            "missing_or_mismatched": [],
                        },
                    },
                ),
            ]
        )
        session.commit()

    with TestClient(app) as client:
        response = client.get(
            "/api/evals/score-history",
            params={
                "window_days": 30,
                "model_name": "filter-model-a:latest",
                "node_id": "jedi",
                "flakiness_min_rate": 0.4,
                "failure_cluster_min_count": 2,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filters"]["window_days"] == 30
    assert payload["filters"]["model_name"] == "filter-model-a:latest"
    assert payload["filters"]["node_id"] == "jedi"
    assert payload["thresholds"]["flakiness_min_rate"] == 0.4
    assert payload["total_runs"] == 2
    assert {run["run_id"] for run in payload["recent_runs"]} == {"eval-filter-run-1", "eval-filter-run-2"}
    assert payload["flaky_cases"][0]["flakiness_rate"] == 0.5
    assert payload["failure_clusters"] == []


def test_eval_baseline_and_exports_report_regression(monkeypatch) -> None:
    class FakeResponse:
        responses = ['{"answer": 42}', '{"answer": 0}']

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"response": self.responses.pop(0)}

    model_name = "baseline-eval-test-model:latest"
    monkeypatch.setattr("backend.app.services.evals.httpx.post", lambda *args, **kwargs: FakeResponse())

    with TestClient(app) as client:
        suite_response = client.post(
            "/api/evals/suites",
            json={"name": "Baseline Suite", "description": "Baseline regression"},
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
                    model_digest="sha256:baseline",
                    available=True,
                    last_seen_at=datetime.now(UTC),
                )
            )
            session.commit()

        first_attempt = client.post(
            f"/api/evals/suites/{suite['suite_id']}/attempts",
            json={"model_name": model_name, "node_id": "jedi"},
        ).json()
        client.post(f"/api/evals/attempts/{first_attempt['attempt_id']}/execute")
        baseline_response = client.post(
            f"/api/evals/suites/{suite['suite_id']}/baseline",
            json={"model_name": model_name, "node_id": "jedi", "minimum_pass_rate": 1.0},
        )

        second_attempt = client.post(
            f"/api/evals/suites/{suite['suite_id']}/attempts",
            json={"model_name": model_name, "node_id": "jedi"},
        ).json()
        client.post(f"/api/evals/attempts/{second_attempt['attempt_id']}/execute")
        history_response = client.get("/api/evals/score-history")
        json_export = client.get("/api/evals/export.json")
        csv_export = client.get("/api/evals/export.csv")

    assert baseline_response.status_code == 200
    history = history_response.json()
    assert any(regression["suite_id"] == suite["suite_id"] for regression in history["regressions"])
    assert json_export.status_code == 200
    assert len(json_export.json()["recent_runs"]) >= 2
    assert csv_export.status_code == 200
    assert "run_id,suite_id" in csv_export.text


def test_create_eval_assisted_summary_uses_selected_model(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "response": "## Situation\nOne eval failure cluster needs review.\n\n## Limits\nAdvisory only."
            }

    model_name = "assisted-summary-test-model:latest"
    monkeypatch.setattr("backend.app.services.evals.httpx.post", lambda *args, **kwargs: FakeResponse())

    with TestClient(app) as client:
        with SessionLocal() as session:
            session.add(
                ModelPlacement(
                    node_id="jedi",
                    model_name=model_name,
                    model_digest="sha256:assisted-summary",
                    available=True,
                    last_seen_at=datetime.now(UTC),
                )
            )
            session.commit()

        response = client.post(
            "/api/evals/assisted-summary",
            json={"model_name": model_name, "node_id": "jedi"},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["detail_type"] == "eval_assisted_summary"
    assert payload["status"] == "success"
    assert payload["metadata_json"]["response_text"].startswith("## Situation")
    assert payload["metadata_json"]["disclaimer"]


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


def test_update_eval_schedule_changes_interval_target_and_mode() -> None:
    first_model = "schedule-update-first:latest"
    second_model = "schedule-update-second:latest"
    with TestClient(app) as client:
        suite_response = client.post(
            "/api/evals/suites",
            json={"name": "Schedule Update Suite", "description": "Editable schedule"},
        )
        suite = suite_response.json()
        client.post(
            f"/api/evals/suites/{suite['suite_id']}/cases",
            json={"name": "Schedule Update Case", "prompt": "Return JSON.", "expected_json": {"ok": True}},
        )

        with SessionLocal() as session:
            for model_name in [first_model, second_model]:
                session.add(
                    ModelPlacement(
                        node_id="jedi",
                        model_name=model_name,
                        model_digest=f"sha256:{model_name}",
                        available=True,
                        last_seen_at=datetime.now(UTC),
                    )
                )
            session.commit()

        create_response = client.post(
            "/api/evals/schedules",
            json={
                "suite_id": suite["suite_id"],
                "model_name": first_model,
                "node_id": "jedi",
                "interval_minutes": 30,
                "enabled": True,
                "auto_execute": False,
            },
        )
        schedule = create_response.json()
        update_response = client.patch(
            f"/api/evals/schedules/{schedule['schedule_id']}",
            json={
                "model_name": second_model,
                "node_id": "jedi",
                "interval_minutes": 45,
                "enabled": False,
                "auto_execute": True,
            },
        )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["model_name"] == second_model
    assert updated["interval_minutes"] == 45
    assert updated["enabled"] is False
    assert updated["auto_execute"] is True


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
