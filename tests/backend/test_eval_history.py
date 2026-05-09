from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.config import BootstrapConfig
from backend.app.models import AppSetting, Base, Node, Run
from backend.app.services.evals import build_score_history, execute_eval_run, score_eval_response


def test_build_score_history_aggregates_eval_runs_by_placement() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    now = datetime.now(UTC)

    with session_factory() as session:
        session.add_all(
            [
                Run(
                    run_id="run-pass",
                    source_type="eval",
                    detail_type="eval_attempt",
                    source_id="eval-suite:suite-1:case:case-1",
                    node_id="jedi",
                    model_name="model-a",
                    action_type="eval",
                    status="success",
                    started_at=now,
                    ended_at=now + timedelta(seconds=1),
                    duration_ms=1000,
                    summary="Eval passed",
                    metadata_json={
                        "suite_id": "suite-1",
                        "suite_name": "Reasoning",
                        "case_id": "case-1",
                        "case_name": "JSON answer",
                        "response_preview": "{\"answer\": 42}",
                        "score": {"passed": True, "score": 1.0, "reason": "expected_subset_matched"},
                    },
                ),
                Run(
                    run_id="run-fail",
                    source_type="eval",
                    detail_type="eval_attempt",
                    source_id="eval-suite:suite-1:case:case-2",
                    node_id="jedi",
                    model_name="model-a",
                    action_type="eval",
                    status="failed",
                    started_at=now - timedelta(seconds=5),
                    ended_at=now - timedelta(seconds=4),
                    duration_ms=1000,
                    summary="Eval failed",
                    metadata_json={
                        "suite_id": "suite-1",
                        "suite_name": "Reasoning",
                        "case_id": "case-2",
                        "case_name": "JSON answer two",
                        "response_preview": "{\"answer\": 24}",
                        "score": {
                            "passed": False,
                            "score": 0.0,
                            "reason": "expected_subset_mismatch",
                            "missing_or_mismatched": ["answer"],
                        },
                    },
                ),
                Run(
                    run_id="run-other",
                    source_type="eval",
                    detail_type="eval_attempt",
                    source_id="eval-suite:suite-1:case:case-1",
                    node_id="bastet",
                    model_name="model-a",
                    action_type="eval",
                    status="success",
                    started_at=now - timedelta(seconds=10),
                    ended_at=now - timedelta(seconds=9),
                    duration_ms=1000,
                    summary="Eval passed remotely",
                    metadata_json={
                        "suite_id": "suite-1",
                        "suite_name": "Reasoning",
                        "case_id": "case-1",
                        "case_name": "JSON answer",
                        "score": {"passed": True, "score": 1.0},
                    },
                ),
            ]
        )
        session.commit()

        history = build_score_history(session)

    assert history["total_runs"] == 3
    assert history["placements"][0]["model_name"] == "model-a"
    assert history["placements"][0]["node_id"] == "bastet"
    assert history["placements"][0]["pass_rate"] == 1.0
    assert history["placements"][1]["node_id"] == "jedi"
    assert history["placements"][1]["pass_rate"] == 0.5
    assert history["suites"][0]["suite_id"] == "suite-1"
    assert history["cases"][0]["case_name"] == "JSON answer"
    assert history["cases"][1]["case_name"] == "JSON answer two"
    assert history["cases"][1]["pass_rate"] == 0.0
    assert history["recent_runs"][0]["response_preview"] == "{\"answer\": 42}"
    assert history["recent_runs"][1]["missing_or_mismatched"] == ["answer"]


def test_execute_eval_run_skips_disabled_local_ollama_endpoints(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    now = datetime.now(UTC)
    called_urls: list[str] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"response": '{"ok": true}'}

    def fake_post(url, *args, **kwargs):
        called_urls.append(url)
        return FakeResponse()

    monkeypatch.setattr("backend.app.services.evals.httpx.post", fake_post)

    with session_factory() as session:
        node = Node(
            node_id="jedi",
            display_name="Jedi",
            base_url="http://127.0.0.1:8000",
            role="primary",
            enabled=True,
            created_from="bootstrap",
        )
        run = Run(
            run_id="eval-run-override",
            source_type="eval",
            detail_type="eval_attempt",
            source_id="eval-suite:suite-1:case:case-1",
            node_id="jedi",
            model_name="model-a",
            action_type="eval",
            status="queued",
            started_at=now,
            summary="Queued eval",
            metadata_json={
                "suite_id": "suite-1",
                "suite_name": "Reasoning",
                "case_id": "case-1",
                "case_name": "JSON answer",
                "prompt": "Return ok true as JSON.",
                "expected_json": {"ok": True},
            },
        )
        session.add(node)
        session.add(run)
        session.add(
            AppSetting(
                key="local_ollama_endpoint_overrides",
                value_json={"disabled": ["http://127.0.0.1:11434"]},
            )
        )
        session.commit()

        updated = execute_eval_run(
            session,
            run,
            node=node,
            config=BootstrapConfig(
                local_ollama_base_urls=["http://127.0.0.1:11434", "http://127.0.0.1:11435"]
            ),
        )
        assert updated.status == "success"

    assert called_urls == ["http://127.0.0.1:11435/api/generate"]


def test_score_eval_response_supports_multiple_score_types() -> None:
    assert score_eval_response('{"answer": 42}', "json_subset", {"answer": 42}, {})["passed"] is True
    assert score_eval_response("hello world", "exact_match", {}, {"expected_text": "hello world"})["passed"] is True
    assert score_eval_response("hello world", "contains", {}, {"expected_text": "world"})["passed"] is True
    assert score_eval_response("ticket-123", "regex", {}, {"pattern": r"ticket-\d+"})["passed"] is True
    assert (
        score_eval_response('{"latency_ms": 750}', "numeric_threshold", {}, {"json_path": "latency_ms", "max": 1000})[
            "passed"
        ]
        is True
    )
    assert (
        score_eval_response(
            '{"answer": 42, "reason": "ok"}',
            "json_schema",
            {},
            {"required": ["answer"], "properties": {"answer": {"const": 42}}},
        )["passed"]
        is True
    )
