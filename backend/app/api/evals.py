from collections import defaultdict
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from backend.app.api.models import _agent_auth_headers
from backend.app.config import DEFAULT_BOOTSTRAP_CONFIG_PATH, load_bootstrap_config
from backend.app.db import SessionLocal
from backend.app.models import EvalCase, EvalSuite, ModelPlacement, Node, Run
from backend.app.services.evals import execute_eval_run
from backend.app.services.runs import serialize_run

router = APIRouter()


class EvalSuiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""


class EvalCaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=1)
    expected_json: dict = Field(default_factory=dict)


class EvalAttemptCreate(BaseModel):
    model_name: str = Field(min_length=1)
    node_id: str = Field(min_length=1)


def _serialize_suites(suites: list[EvalSuite], cases: list[EvalCase]) -> list[dict]:
    cases_by_suite: dict[str, list[dict]] = defaultdict(list)
    for case in cases:
        cases_by_suite[case.suite_id].append(
            {
                "case_id": case.case_id,
                "name": case.name,
                "prompt": case.prompt,
                "expected_json": case.expected_json,
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
                sort_order=case_count,
            )
        )
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

        attempt_id = str(uuid4())
        started_at = datetime.now(UTC)
        runs: list[Run] = []
        for eval_case in cases:
            run = Run(
                run_id=str(uuid4()),
                source_type="eval",
                detail_type="eval_attempt",
                source_id=f"eval-suite:{suite_id}:case:{eval_case.case_id}",
                node_id=payload.node_id,
                model_name=payload.model_name,
                action_type="eval",
                status="queued",
                started_at=started_at,
                summary=f"Queued eval case '{eval_case.name}' for {payload.model_name} on {payload.node_id}",
                metadata_json={
                    "attempt_id": attempt_id,
                    "suite_id": suite.suite_id,
                    "suite_name": suite.name,
                    "case_id": eval_case.case_id,
                    "case_name": eval_case.name,
                    "prompt": eval_case.prompt,
                    "expected_json": eval_case.expected_json,
                    "sort_order": eval_case.sort_order,
                },
            )
            session.add(run)
            runs.append(run)

        session.commit()

        return {
            "attempt_id": attempt_id,
            "suite_id": suite.suite_id,
            "suite_name": suite.name,
            "model_name": payload.model_name,
            "node_id": payload.node_id,
            "run_count": len(runs),
            "runs": [serialize_run(run) for run in runs],
        }


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
            auth_headers=_agent_auth_headers(),
        )
        return serialize_run(updated)
