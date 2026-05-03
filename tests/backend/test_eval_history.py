from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models import Base, Run
from backend.app.services.evals import build_score_history


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
