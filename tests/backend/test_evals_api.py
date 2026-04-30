from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import ModelPlacement


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
