from collections import defaultdict

from fastapi import APIRouter
from sqlalchemy import select

from backend.app.db import SessionLocal
from backend.app.models import EvalCase, EvalSuite

router = APIRouter()


@router.get("/evals/suites")
def list_eval_suites() -> list[dict]:
    with SessionLocal() as session:
        suites = session.scalars(select(EvalSuite).order_by(EvalSuite.name)).all()
        cases = session.scalars(select(EvalCase).order_by(EvalCase.suite_id, EvalCase.sort_order, EvalCase.name)).all()

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
