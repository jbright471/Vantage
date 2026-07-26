from collections import defaultdict
import csv
import io
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from backend.app.config import DEFAULT_BOOTSTRAP_CONFIG_PATH, load_bootstrap_config
from backend.app.db import SessionLocal
from backend.app.models import EvalCase, EvalSchedule, EvalSuite, ModelPlacement, Node, Run
from backend.app.services.eval_schedules import (
    create_eval_schedule,
    list_eval_schedules,
    queue_eval_schedule_now,
    serialize_eval_schedule,
    update_eval_schedule,
)
from backend.app.services.eval_presets import (
    delete_eval_intelligence_preset,
    list_eval_intelligence_presets,
    upsert_eval_intelligence_preset,
)
from backend.app.services.evals import (
    build_eval_assisted_summary_run,
    build_score_history,
    execute_eval_run,
    queue_eval_case_runs,
)
from backend.app.services.runs import serialize_run

router = APIRouter()
MAX_EVAL_CASES_PER_SUITE = 100
MAX_EVAL_PROMPT_CHARS = 16000
STARTER_EVAL_TEMPLATE_ID = "vantage-starter-smoke-v1"
STARTER_EVAL_CASES = (
    {
        "name": "Structured JSON handshake",
        "prompt": 'Return exactly this JSON object and no Markdown: {"vantage_smoke":true,"answer":7}',
        "expected_json": {"vantage_smoke": True, "answer": 7},
        "score_type": "json_subset",
        "score_config_json": {},
    },
    {
        "name": "Exact instruction following",
        "prompt": "Return exactly VANTAGE_OK and nothing else.",
        "expected_json": {},
        "score_type": "exact_match",
        "score_config_json": {"expected_text": "VANTAGE_OK"},
    },
)


class EvalSuiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)


class EvalSuiteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)


class EvalCaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=1, max_length=MAX_EVAL_PROMPT_CHARS)
    expected_json: dict = Field(default_factory=dict)
    score_type: str = "json_subset"
    score_config_json: dict = Field(default_factory=dict)


class EvalCaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    prompt: str | None = Field(default=None, min_length=1, max_length=MAX_EVAL_PROMPT_CHARS)
    expected_json: dict | None = None
    score_type: str | None = None
    score_config_json: dict | None = None
    sort_order: int | None = Field(default=None, ge=0)


class EvalAttemptCreate(BaseModel):
    model_name: str = Field(min_length=1)
    node_id: str = Field(min_length=1)


class EvalScheduleCreate(BaseModel):
    suite_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    interval_minutes: int = Field(ge=1, le=10080)
    enabled: bool = True
    auto_execute: bool = False


class EvalScheduleUpdate(BaseModel):
    enabled: bool | None = None
    auto_execute: bool | None = None
    model_name: str | None = Field(default=None, min_length=1)
    node_id: str | None = Field(default=None, min_length=1)
    interval_minutes: int | None = Field(default=None, ge=1, le=10080)


class EvalBaselineCreate(BaseModel):
    model_name: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    minimum_pass_rate: float = Field(ge=0, le=1)


class EvalAssistedSummaryCreate(BaseModel):
    model_name: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    filter_model_name: str | None = None
    filter_node_id: str | None = None
    window_days: int = Field(default=30, ge=1, le=3650)
    flakiness_min_rate: float = Field(default=0.2, ge=0, le=1)
    failure_cluster_min_count: int = Field(default=2, ge=1, le=100)


class EvalHistoryQuery(BaseModel):
    window_days: int = Field(default=30, ge=1, le=3650)
    model_name: str | None = None
    node_id: str | None = None
    flakiness_min_rate: float = Field(default=0.2, ge=0, le=1)
    failure_cluster_min_count: int = Field(default=2, ge=1, le=100)
    recent_limit: int = Field(default=20, ge=1, le=200)


class EvalIntelligencePresetControls(BaseModel):
    window_days: str = Field(min_length=1)
    placement_key: str = ""
    flakiness_min_rate: str = Field(min_length=1)
    failure_cluster_min_count: str = Field(min_length=1)


class EvalIntelligencePresetUpsert(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    controls: EvalIntelligencePresetControls


def _serialize_suites(suites: list[EvalSuite], cases: list[EvalCase]) -> list[dict]:
    cases_by_suite: dict[str, list[dict]] = defaultdict(list)
    for case in cases:
        cases_by_suite[case.suite_id].append(
            {
                "case_id": case.case_id,
                "name": case.name,
                "prompt": case.prompt,
                "expected_json": case.expected_json,
                "score_type": case.score_type,
                "score_config_json": case.score_config_json,
                "sort_order": case.sort_order,
            }
        )

    return [
        {
            "suite_id": suite.suite_id,
            "name": suite.name,
            "description": suite.description,
            "created_at": suite.created_at.isoformat(),
            "metadata_json": suite.metadata_json,
            "case_count": len(cases_by_suite[suite.suite_id]),
            "cases": cases_by_suite[suite.suite_id],
        }
        for suite in suites
    ]


def _get_suite_payload(session, suite_id: str) -> dict:
    suite = session.get(EvalSuite, suite_id)
    if suite is None:
        raise HTTPException(status_code=404, detail=f"Unknown eval suite '{suite_id}'")
    cases = session.scalars(
        select(EvalCase).where(EvalCase.suite_id == suite_id).order_by(EvalCase.sort_order, EvalCase.name)
    ).all()
    return _serialize_suites([suite], cases)[0]


@router.get("/evals/suites")
def list_eval_suites() -> list[dict]:
    with SessionLocal() as session:
        suites = session.scalars(select(EvalSuite).order_by(EvalSuite.name)).all()
        cases = session.scalars(select(EvalCase).order_by(EvalCase.suite_id, EvalCase.sort_order, EvalCase.name)).all()

    return _serialize_suites(suites, cases)


@router.post("/evals/starter-suite", status_code=201)
def install_starter_eval_suite() -> dict:
    with SessionLocal() as session:
        suites = session.scalars(select(EvalSuite)).all()
        existing = next(
            (
                suite
                for suite in suites
                if (suite.metadata_json or {}).get("template_id") == STARTER_EVAL_TEMPLATE_ID
            ),
            None,
        )
        if existing is not None:
            return _get_suite_payload(session, existing.suite_id)

        suite = EvalSuite(
            suite_id=str(uuid4()),
            name="Vantage Starter Smoke",
            description="Repeatable local-model readiness checks for structured output and instruction following.",
            created_at=datetime.now(UTC),
            metadata_json={"template_id": STARTER_EVAL_TEMPLATE_ID, "template_version": 1},
        )
        session.add(suite)
        for sort_order, case_template in enumerate(STARTER_EVAL_CASES):
            session.add(
                EvalCase(
                    case_id=str(uuid4()),
                    suite_id=suite.suite_id,
                    sort_order=sort_order,
                    **case_template,
                )
            )
        session.commit()
        return _get_suite_payload(session, suite.suite_id)


def _eval_history_query(
    window_days: int = Query(default=30, ge=1, le=3650),
    model_name: str | None = Query(default=None),
    node_id: str | None = Query(default=None),
    flakiness_min_rate: float = Query(default=0.2, ge=0, le=1),
    failure_cluster_min_count: int = Query(default=2, ge=1, le=100),
    recent_limit: int = Query(default=20, ge=1, le=200),
) -> EvalHistoryQuery:
    return EvalHistoryQuery(
        window_days=window_days,
        model_name=model_name,
        node_id=node_id,
        flakiness_min_rate=flakiness_min_rate,
        failure_cluster_min_count=failure_cluster_min_count,
        recent_limit=recent_limit,
    )


def _build_eval_history_payload(session, query: EvalHistoryQuery) -> dict:
    history = build_score_history(
        session,
        window_days=query.window_days,
        model_name=query.model_name,
        node_id=query.node_id,
        flakiness_min_rate=query.flakiness_min_rate,
        failure_cluster_min_count=query.failure_cluster_min_count,
        recent_limit=query.recent_limit,
    )
    history["regressions"] = _build_eval_regressions(session, history)
    history["schedule_health"] = _build_eval_schedule_health(
        session,
        model_name=query.model_name,
        node_id=query.node_id,
    )
    history["operator_summary"] = _build_eval_operator_summary(history)
    return history


@router.get("/evals/score-history")
def get_eval_score_history(query: EvalHistoryQuery = Depends(_eval_history_query)) -> dict:
    with SessionLocal() as session:
        return _build_eval_history_payload(session, query)


@router.get("/evals/intelligence-presets")
def get_eval_intelligence_presets() -> dict:
    with SessionLocal() as session:
        presets = list_eval_intelligence_presets(session)
    return {"format": "vantage.eval-intelligence-presets.v1", "count": len(presets), "presets": presets}


@router.put("/evals/intelligence-presets")
def save_eval_intelligence_preset(payload: EvalIntelligencePresetUpsert) -> dict:
    with SessionLocal() as session:
        return upsert_eval_intelligence_preset(session, payload.model_dump())


@router.delete("/evals/intelligence-presets/{preset_id}")
def remove_eval_intelligence_preset(preset_id: str) -> dict:
    with SessionLocal() as session:
        deleted = delete_eval_intelligence_preset(session, preset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Unknown eval intelligence preset '{preset_id}'")
    return {"deleted": True, "preset_id": preset_id}


@router.get("/evals/export.json")
def export_eval_history_json(query: EvalHistoryQuery = Depends(_eval_history_query)) -> dict:
    with SessionLocal() as session:
        return _build_eval_history_payload(session, query)


@router.get("/evals/export.csv")
def export_eval_history_csv(query: EvalHistoryQuery = Depends(_eval_history_query)) -> Response:
    with SessionLocal() as session:
        rows = _build_eval_history_payload(session, query)["recent_runs"]

    buffer = io.StringIO()
    fieldnames = ["run_id", "suite_id", "suite_name", "case_id", "case_name", "model_name", "node_id", "passed", "score", "started_at"]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field) for field in fieldnames})
    return Response(content=buffer.getvalue(), media_type="text/csv")


@router.post("/evals/assisted-summary", status_code=201)
def create_eval_assisted_summary(payload: EvalAssistedSummaryCreate) -> dict:
    config = load_bootstrap_config(DEFAULT_BOOTSTRAP_CONFIG_PATH)
    with SessionLocal() as session:
        node = session.get(Node, payload.node_id)
        if node is None:
            raise HTTPException(status_code=404, detail=f"Unknown node '{payload.node_id}'")
        placement = session.scalar(
            select(ModelPlacement).where(
                ModelPlacement.node_id == payload.node_id,
                ModelPlacement.model_name == payload.model_name,
                ModelPlacement.available.is_(True),
            )
        )
        if placement is None:
            raise HTTPException(
                status_code=409,
                detail=f"Model '{payload.model_name}' is not available on node '{payload.node_id}'",
            )

        history = _build_eval_history_payload(
            session,
            EvalHistoryQuery(
                window_days=payload.window_days,
                model_name=payload.filter_model_name,
                node_id=payload.filter_node_id,
                flakiness_min_rate=payload.flakiness_min_rate,
                failure_cluster_min_count=payload.failure_cluster_min_count,
            ),
        )
        run = build_eval_assisted_summary_run(
            session,
            history=history,
            model_name=payload.model_name,
            node=node,
            config=config,
        )
        return serialize_run(run)


@router.get("/evals/schedules")
def get_eval_schedules() -> list[dict]:
    with SessionLocal() as session:
        return list_eval_schedules(session)


@router.post("/evals/schedules", status_code=201)
def create_schedule(payload: EvalScheduleCreate) -> dict:
    with SessionLocal() as session:
        try:
            schedule = create_eval_schedule(
                session,
                suite_id=payload.suite_id,
                model_name=payload.model_name,
                node_id=payload.node_id,
                interval_minutes=payload.interval_minutes,
                enabled=payload.enabled,
                auto_execute=payload.auto_execute,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        session.commit()
        suite = session.get(EvalSuite, schedule.suite_id)
        return serialize_eval_schedule(schedule, suite.name if suite else None)


@router.delete("/evals/schedules/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: str) -> Response:
    with SessionLocal() as session:
        schedule = session.get(EvalSchedule, schedule_id)
        if schedule is None:
            raise HTTPException(status_code=404, detail=f"Unknown eval schedule '{schedule_id}'")
        session.delete(schedule)
        session.commit()
        return Response(status_code=204)


@router.patch("/evals/schedules/{schedule_id}")
def update_schedule(schedule_id: str, payload: EvalScheduleUpdate) -> dict:
    with SessionLocal() as session:
        if payload.model_name is not None or payload.node_id is not None or payload.interval_minutes is not None:
            schedule = session.get(EvalSchedule, schedule_id)
            if schedule is None:
                raise HTTPException(status_code=404, detail=f"Unknown eval schedule '{schedule_id}'")
            next_model = payload.model_name or schedule.model_name
            next_node = payload.node_id or schedule.node_id
            placement = session.scalar(
                select(ModelPlacement).where(
                    ModelPlacement.node_id == next_node,
                    ModelPlacement.model_name == next_model,
                    ModelPlacement.available.is_(True),
                )
            )
            if placement is None:
                raise HTTPException(
                    status_code=409,
                    detail=f"Model '{next_model}' is not available on node '{next_node}'",
                )
            if payload.model_name is not None:
                schedule.model_name = payload.model_name
            if payload.node_id is not None:
                schedule.node_id = payload.node_id
            if payload.interval_minutes is not None:
                schedule.interval_minutes = payload.interval_minutes
                schedule.next_run_at = datetime.now(UTC) + timedelta(minutes=payload.interval_minutes)
            if payload.enabled is not None:
                schedule.enabled = payload.enabled
            if payload.auto_execute is not None:
                schedule.auto_execute = payload.auto_execute
            schedule.updated_at = datetime.now(UTC)
            session.commit()
            suite = session.get(EvalSuite, schedule.suite_id)
            return serialize_eval_schedule(schedule, suite.name if suite else None)

        schedule = update_eval_schedule(
            session,
            schedule_id,
            enabled=payload.enabled,
            auto_execute=payload.auto_execute,
        )
        if schedule is None:
            raise HTTPException(status_code=404, detail=f"Unknown eval schedule '{schedule_id}'")
        session.commit()
        suite = session.get(EvalSuite, schedule.suite_id)
        return serialize_eval_schedule(schedule, suite.name if suite else None)


@router.post("/evals/schedules/{schedule_id}/queue-now", status_code=201)
def queue_schedule_now(schedule_id: str) -> dict:
    with SessionLocal() as session:
        try:
            result = queue_eval_schedule_now(session, schedule_id)
        except ValueError as exc:
            message = str(exc)
            status_code = 404 if message.startswith("Unknown eval schedule") else 409
            raise HTTPException(status_code=status_code, detail=message) from exc
        session.commit()
        schedule = session.get(EvalSchedule, schedule_id)
        suite = session.get(EvalSuite, result["suite_id"])
        return {
            "attempt_id": result["attempt_id"],
            "suite_id": result["suite_id"],
            "suite_name": result["suite_name"],
            "model_name": result["model_name"],
            "node_id": result["node_id"],
            "run_count": result["run_count"],
            "runs": [serialize_run(run) for run in result["runs"]],
            "schedule": serialize_eval_schedule(schedule, suite.name if suite else None) if schedule else None,
        }


@router.post("/evals/suites", status_code=201)
def create_eval_suite(payload: EvalSuiteCreate) -> dict:
    with SessionLocal() as session:
        suite = EvalSuite(
            suite_id=str(uuid4()),
            name=payload.name.strip(),
            description=payload.description.strip(),
            created_at=datetime.now(UTC),
            metadata_json={},
        )
        session.add(suite)
        session.commit()
        return _get_suite_payload(session, suite.suite_id)


@router.patch("/evals/suites/{suite_id}")
def update_eval_suite(suite_id: str, payload: EvalSuiteUpdate) -> dict:
    with SessionLocal() as session:
        suite = session.get(EvalSuite, suite_id)
        if suite is None:
            raise HTTPException(status_code=404, detail=f"Unknown eval suite '{suite_id}'")
        if payload.name is not None:
            suite.name = payload.name.strip()
        if payload.description is not None:
            suite.description = payload.description.strip()
        session.commit()
        return _get_suite_payload(session, suite_id)


@router.post("/evals/suites/{suite_id}/duplicate", status_code=201)
def duplicate_eval_suite(suite_id: str) -> dict:
    with SessionLocal() as session:
        suite = session.get(EvalSuite, suite_id)
        if suite is None:
            raise HTTPException(status_code=404, detail=f"Unknown eval suite '{suite_id}'")
        cases = session.scalars(
            select(EvalCase).where(EvalCase.suite_id == suite_id).order_by(EvalCase.sort_order, EvalCase.name)
        ).all()
        duplicate = EvalSuite(
            suite_id=str(uuid4()),
            name=f"{suite.name} Copy",
            description=suite.description,
            created_at=datetime.now(UTC),
            metadata_json=dict(suite.metadata_json or {}),
        )
        session.add(duplicate)
        for eval_case in cases:
            session.add(
                EvalCase(
                    case_id=str(uuid4()),
                    suite_id=duplicate.suite_id,
                    name=eval_case.name,
                    prompt=eval_case.prompt,
                    expected_json=dict(eval_case.expected_json or {}),
                    score_type=eval_case.score_type,
                    score_config_json=dict(eval_case.score_config_json or {}),
                    sort_order=eval_case.sort_order,
                )
            )
        session.commit()
        return _get_suite_payload(session, duplicate.suite_id)


@router.get("/evals/suites/{suite_id}/export")
def export_eval_suite(suite_id: str) -> dict:
    with SessionLocal() as session:
        payload = _get_suite_payload(session, suite_id)
        return {
            "name": payload["name"],
            "description": payload["description"],
            "metadata_json": payload["metadata_json"],
            "cases": payload["cases"],
        }


@router.post("/evals/suites/import", status_code=201)
def import_eval_suite(payload: dict) -> dict:
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        raise HTTPException(status_code=422, detail="Eval suite cases must be a list")
    if len(cases) > MAX_EVAL_CASES_PER_SUITE:
        raise HTTPException(status_code=413, detail=f"Eval suites are limited to {MAX_EVAL_CASES_PER_SUITE} cases")
    for item in cases:
        if isinstance(item, dict) and len(str(item.get("prompt") or "")) > MAX_EVAL_PROMPT_CHARS:
            raise HTTPException(status_code=413, detail="An imported eval prompt exceeds the configured size limit")

    with SessionLocal() as session:
        suite = EvalSuite(
            suite_id=str(uuid4()),
            name=str(payload.get("name") or "Imported suite").strip(),
            description=str(payload.get("description") or "").strip(),
            created_at=datetime.now(UTC),
            metadata_json=payload.get("metadata_json") if isinstance(payload.get("metadata_json"), dict) else {},
        )
        session.add(suite)
        for index, item in enumerate(cases):
            if not isinstance(item, dict):
                continue
            session.add(
                EvalCase(
                    case_id=str(uuid4()),
                    suite_id=suite.suite_id,
                    name=str(item.get("name") or f"Imported Case {index + 1}").strip()[:120],
                    prompt=str(item.get("prompt") or "").strip(),
                    expected_json=item.get("expected_json") if isinstance(item.get("expected_json"), dict) else {},
                    score_type=str(item.get("score_type") or "json_subset")[:64],
                    score_config_json=item.get("score_config_json")
                    if isinstance(item.get("score_config_json"), dict)
                    else {},
                    sort_order=int(item.get("sort_order") or index),
                )
            )
        session.commit()
        return _get_suite_payload(session, suite.suite_id)


@router.delete("/evals/suites/{suite_id}", status_code=204)
def delete_eval_suite(suite_id: str) -> Response:
    with SessionLocal() as session:
        suite = session.get(EvalSuite, suite_id)
        if suite is None:
            raise HTTPException(status_code=404, detail=f"Unknown eval suite '{suite_id}'")
        case_count = session.scalar(select(func.count()).select_from(EvalCase).where(EvalCase.suite_id == suite_id)) or 0
        if case_count:
            raise HTTPException(status_code=409, detail="Delete eval cases before deleting this suite")
        schedule_count = (
            session.scalar(select(func.count()).select_from(EvalSchedule).where(EvalSchedule.suite_id == suite_id))
            or 0
        )
        if schedule_count:
            raise HTTPException(status_code=409, detail="Delete eval schedules before deleting this suite")
        session.delete(suite)
        session.commit()
        return Response(status_code=204)


@router.post("/evals/suites/{suite_id}/cases", status_code=201)
def create_eval_case(suite_id: str, payload: EvalCaseCreate) -> dict:
    with SessionLocal() as session:
        suite = session.get(EvalSuite, suite_id)
        if suite is None:
            raise HTTPException(status_code=404, detail=f"Unknown eval suite '{suite_id}'")
        case_count = session.scalar(select(func.count()).select_from(EvalCase).where(EvalCase.suite_id == suite_id)) or 0
        session.add(
            EvalCase(
                case_id=str(uuid4()),
                suite_id=suite_id,
                name=payload.name.strip(),
                prompt=payload.prompt.strip(),
                expected_json=payload.expected_json,
                score_type=payload.score_type,
                score_config_json=payload.score_config_json,
                sort_order=case_count,
            )
        )
        session.commit()
        return _get_suite_payload(session, suite_id)


@router.patch("/evals/suites/{suite_id}/cases/{case_id}")
def update_eval_case(suite_id: str, case_id: str, payload: EvalCaseUpdate) -> dict:
    with SessionLocal() as session:
        eval_case = session.get(EvalCase, case_id)
        if eval_case is None or eval_case.suite_id != suite_id:
            raise HTTPException(status_code=404, detail=f"Unknown eval case '{case_id}'")
        if payload.name is not None:
            eval_case.name = payload.name.strip()
        if payload.prompt is not None:
            eval_case.prompt = payload.prompt.strip()
        if payload.expected_json is not None:
            eval_case.expected_json = payload.expected_json
        if payload.score_type is not None:
            eval_case.score_type = payload.score_type
        if payload.score_config_json is not None:
            eval_case.score_config_json = payload.score_config_json
        if payload.sort_order is not None:
            eval_case.sort_order = payload.sort_order
        session.commit()
        return _get_suite_payload(session, suite_id)


@router.post("/evals/suites/{suite_id}/cases/{case_id}/duplicate", status_code=201)
def duplicate_eval_case(suite_id: str, case_id: str) -> dict:
    with SessionLocal() as session:
        eval_case = session.get(EvalCase, case_id)
        if eval_case is None or eval_case.suite_id != suite_id:
            raise HTTPException(status_code=404, detail=f"Unknown eval case '{case_id}'")
        case_count = session.scalar(select(func.count()).select_from(EvalCase).where(EvalCase.suite_id == suite_id)) or 0
        session.add(
            EvalCase(
                case_id=str(uuid4()),
                suite_id=suite_id,
                name=f"{eval_case.name} Copy",
                prompt=eval_case.prompt,
                expected_json=dict(eval_case.expected_json or {}),
                score_type=eval_case.score_type,
                score_config_json=dict(eval_case.score_config_json or {}),
                sort_order=case_count,
            )
        )
        session.commit()
        return _get_suite_payload(session, suite_id)


@router.delete("/evals/suites/{suite_id}/cases/{case_id}")
def delete_eval_case(suite_id: str, case_id: str) -> dict:
    with SessionLocal() as session:
        suite = session.get(EvalSuite, suite_id)
        if suite is None:
            raise HTTPException(status_code=404, detail=f"Unknown eval suite '{suite_id}'")
        eval_case = session.get(EvalCase, case_id)
        if eval_case is None or eval_case.suite_id != suite_id:
            raise HTTPException(status_code=404, detail=f"Unknown eval case '{case_id}'")
        session.delete(eval_case)
        session.commit()
        return _get_suite_payload(session, suite_id)


@router.post("/evals/suites/{suite_id}/attempts", status_code=201)
def queue_eval_attempt(suite_id: str, payload: EvalAttemptCreate) -> dict:
    with SessionLocal() as session:
        suite = session.get(EvalSuite, suite_id)
        if suite is None:
            raise HTTPException(status_code=404, detail=f"Unknown eval suite '{suite_id}'")

        node = session.get(Node, payload.node_id)
        if node is None:
            raise HTTPException(status_code=404, detail=f"Unknown node '{payload.node_id}'")

        placement = session.scalar(
            select(ModelPlacement).where(
                ModelPlacement.node_id == payload.node_id,
                ModelPlacement.model_name == payload.model_name,
                ModelPlacement.available.is_(True),
            )
        )
        if placement is None:
            raise HTTPException(
                status_code=404,
                detail=f"Model '{payload.model_name}' is not available on node '{payload.node_id}'",
            )

        cases = session.scalars(
            select(EvalCase).where(EvalCase.suite_id == suite_id).order_by(EvalCase.sort_order, EvalCase.name)
        ).all()
        if not cases:
            raise HTTPException(status_code=409, detail=f"Eval suite '{suite_id}' has no cases to queue")

        started_at = datetime.now(UTC)
        result = queue_eval_case_runs(
            session,
            suite=suite,
            cases=cases,
            model_name=payload.model_name,
            node_id=payload.node_id,
            trigger="manual",
            started_at=started_at,
        )

        session.commit()

        return {
            "attempt_id": result["attempt_id"],
            "suite_id": suite.suite_id,
            "suite_name": suite.name,
            "model_name": payload.model_name,
            "node_id": payload.node_id,
            "run_count": result["run_count"],
            "runs": [serialize_run(run) for run in result["runs"]],
        }


@router.post("/evals/attempts/{attempt_id}/execute")
def execute_eval_attempt_batch(attempt_id: str) -> dict:
    config = load_bootstrap_config(DEFAULT_BOOTSTRAP_CONFIG_PATH)
    with SessionLocal() as session:
        runs = session.scalars(
            select(Run)
            .where(Run.detail_type == "eval_attempt")
            .where(Run.metadata_json["attempt_id"].as_string() == attempt_id)
            .order_by(Run.started_at, Run.run_id)
        ).all()
        if not runs:
            raise HTTPException(status_code=404, detail=f"Unknown eval attempt '{attempt_id}'")
        updated_runs = []
        for run in runs:
            if run.status == "running":
                continue
            node = session.get(Node, run.node_id)
            if node is None:
                continue
            updated_runs.append(
                execute_eval_run(
                    session,
                    run,
                    node=node,
                    config=config,
                )
            )
        return {
            "attempt_id": attempt_id,
            "runs_executed": len(updated_runs),
            "runs": [serialize_run(run) for run in updated_runs],
        }


@router.post("/evals/suites/{suite_id}/baseline")
def create_eval_baseline(suite_id: str, payload: EvalBaselineCreate) -> dict:
    with SessionLocal() as session:
        suite = session.get(EvalSuite, suite_id)
        if suite is None:
            raise HTTPException(status_code=404, detail=f"Unknown eval suite '{suite_id}'")
        metadata = dict(suite.metadata_json or {})
        baselines = list(metadata.get("baselines") or [])
        baseline = {
            "suite_id": suite_id,
            "model_name": payload.model_name,
            "node_id": payload.node_id,
            "minimum_pass_rate": payload.minimum_pass_rate,
            "created_at": datetime.now(UTC).isoformat(),
        }
        baselines = [
            item
            for item in baselines
            if not (
                isinstance(item, dict)
                and item.get("model_name") == payload.model_name
                and item.get("node_id") == payload.node_id
            )
        ]
        baselines.append(baseline)
        metadata["baselines"] = baselines
        suite.metadata_json = metadata
        session.commit()
        return baseline


@router.post("/evals/runs/{run_id}/execute")
def execute_eval_attempt_run(run_id: str) -> dict:
    config = load_bootstrap_config(DEFAULT_BOOTSTRAP_CONFIG_PATH)
    with SessionLocal() as session:
        run = session.get(Run, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"Unknown eval run '{run_id}'")
        if run.detail_type != "eval_attempt":
            raise HTTPException(status_code=409, detail=f"Run '{run_id}' is not an eval attempt")
        if run.status == "running":
            raise HTTPException(status_code=409, detail=f"Run '{run_id}' is already running")

        node = session.get(Node, run.node_id)
        if node is None:
            raise HTTPException(status_code=404, detail=f"Unknown node '{run.node_id}'")

        updated = execute_eval_run(
            session,
            run,
            node=node,
            config=config,
        )
        return serialize_run(updated)


def _build_eval_regressions(session, history: dict) -> list[dict]:
    regressions: list[dict] = []
    suites = session.scalars(select(EvalSuite)).all()
    for suite in suites:
        for baseline in (suite.metadata_json or {}).get("baselines", []):
            if not isinstance(baseline, dict):
                continue
            matching_rows = [
                row
                for row in history.get("recent_runs", [])
                if row.get("suite_id") == suite.suite_id
                and row.get("model_name") == baseline.get("model_name")
                and row.get("node_id") == baseline.get("node_id")
            ]
            if not matching_rows:
                continue
            pass_rate = round(sum(1 for row in matching_rows if row.get("passed")) / len(matching_rows), 4)
            minimum = float(baseline.get("minimum_pass_rate") or 0)
            if pass_rate < minimum:
                regressions.append(
                    {
                        "suite_id": suite.suite_id,
                        "suite_name": suite.name,
                        "model_name": baseline.get("model_name"),
                        "node_id": baseline.get("node_id"),
                        "minimum_pass_rate": minimum,
                        "current_pass_rate": pass_rate,
                    }
                )
    return regressions


def _build_eval_schedule_health(session, *, model_name: str | None = None, node_id: str | None = None) -> list[dict]:
    rows = []
    query = select(EvalSchedule)
    if model_name:
        query = query.where(EvalSchedule.model_name == model_name)
    if node_id:
        query = query.where(EvalSchedule.node_id == node_id)
    for schedule in session.scalars(query).all():
        metadata = schedule.metadata_json or {}
        last_auto_execute = metadata.get("last_auto_execute") if isinstance(metadata.get("last_auto_execute"), dict) else {}
        rows.append(
            {
                "schedule_id": schedule.schedule_id,
                "suite_id": schedule.suite_id,
                "model_name": schedule.model_name,
                "node_id": schedule.node_id,
                "enabled": schedule.enabled,
                "auto_execute": schedule.auto_execute,
                "next_run_at": schedule.next_run_at.isoformat(),
                "last_queued_at": schedule.last_queued_at.isoformat() if schedule.last_queued_at else None,
                "last_runs_executed": int(last_auto_execute.get("runs_executed") or 0),
                "last_runs_failed": int(last_auto_execute.get("runs_failed") or 0),
                "status": "warning" if int(last_auto_execute.get("runs_failed") or 0) > 0 else "healthy",
            }
        )
    return rows


def _build_eval_operator_summary(history: dict) -> dict:
    regressions = history.get("regressions") or []
    flaky_cases = history.get("flaky_cases") or []
    failure_clusters = history.get("failure_clusters") or []
    if regressions:
        headline = f"{len(regressions)} eval baseline regression{'s' if len(regressions) != 1 else ''} need review."
    elif failure_clusters:
        headline = f"{len(failure_clusters)} repeated eval failure cluster{'s' if len(failure_clusters) != 1 else ''} detected."
    elif flaky_cases:
        headline = f"{len(flaky_cases)} flaky eval case{'s' if len(flaky_cases) != 1 else ''} detected."
    elif history.get("total_runs", 0) > 0:
        headline = "Eval history is clean against current deterministic checks."
    else:
        headline = "No scored eval runs yet."
    return {
        "headline": headline,
        "regression_count": len(regressions),
        "flaky_case_count": len(flaky_cases),
        "failure_cluster_count": len(failure_clusters),
    }
