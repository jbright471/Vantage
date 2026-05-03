from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import EvalCase, EvalSchedule, EvalSuite, ModelPlacement, Node
from backend.app.services.evals import queue_eval_case_runs


def serialize_eval_schedule(schedule: EvalSchedule, suite_name: str | None = None) -> dict[str, Any]:
    return {
        "schedule_id": schedule.schedule_id,
        "suite_id": schedule.suite_id,
        "suite_name": suite_name,
        "model_name": schedule.model_name,
        "node_id": schedule.node_id,
        "interval_minutes": schedule.interval_minutes,
        "enabled": schedule.enabled,
        "auto_execute": schedule.auto_execute,
        "created_at": schedule.created_at.isoformat(),
        "updated_at": schedule.updated_at.isoformat(),
        "next_run_at": schedule.next_run_at.isoformat(),
        "last_queued_at": schedule.last_queued_at.isoformat() if schedule.last_queued_at else None,
        "metadata_json": schedule.metadata_json,
    }


def list_eval_schedules(session: Session) -> list[dict[str, Any]]:
    schedules = session.scalars(select(EvalSchedule).order_by(EvalSchedule.created_at.desc())).all()
    suite_names = {
        suite.suite_id: suite.name
        for suite in session.scalars(select(EvalSuite).where(EvalSuite.suite_id.in_([s.suite_id for s in schedules]))).all()
    }
    return [serialize_eval_schedule(schedule, suite_names.get(schedule.suite_id)) for schedule in schedules]


def create_eval_schedule(
    session: Session,
    *,
    suite_id: str,
    model_name: str,
    node_id: str,
    interval_minutes: int,
    enabled: bool = True,
    auto_execute: bool = False,
    now: datetime | None = None,
) -> EvalSchedule:
    current_time = now or datetime.now(UTC)
    _load_schedule_target(session, suite_id=suite_id, model_name=model_name, node_id=node_id)

    schedule = EvalSchedule(
        schedule_id=str(uuid4()),
        suite_id=suite_id,
        model_name=model_name,
        node_id=node_id,
        interval_minutes=interval_minutes,
        enabled=enabled,
        auto_execute=auto_execute,
        created_at=current_time,
        updated_at=current_time,
        next_run_at=current_time + timedelta(minutes=interval_minutes),
        metadata_json={},
    )
    session.add(schedule)
    return schedule


def update_eval_schedule(
    session: Session,
    schedule_id: str,
    *,
    enabled: bool | None = None,
    auto_execute: bool | None = None,
) -> EvalSchedule | None:
    schedule = session.get(EvalSchedule, schedule_id)
    if schedule is None:
        return None
    if enabled is not None:
        schedule.enabled = enabled
    if auto_execute is not None:
        schedule.auto_execute = auto_execute
    schedule.updated_at = datetime.now(UTC)
    return schedule


def queue_due_eval_schedules(session: Session, *, now: datetime | None = None) -> dict[str, int]:
    current_time = now or datetime.now(UTC)
    schedules = session.scalars(
        select(EvalSchedule)
        .where(EvalSchedule.enabled.is_(True))
        .where(EvalSchedule.next_run_at <= current_time)
        .order_by(EvalSchedule.next_run_at)
    ).all()

    summary: dict[str, Any] = {
        "schedules_checked": len(schedules),
        "schedules_queued": 0,
        "runs_queued": 0,
        "schedules_failed": 0,
        "auto_execute_run_ids": [],
        "auto_execute_schedule_ids": [],
    }
    for schedule in schedules:
        try:
            suite, cases = _load_schedule_target(
                session,
                suite_id=schedule.suite_id,
                model_name=schedule.model_name,
                node_id=schedule.node_id,
            )
            result = queue_eval_case_runs(
                session,
                suite=suite,
                cases=cases,
                model_name=schedule.model_name,
                node_id=schedule.node_id,
                trigger="schedule",
                schedule_id=schedule.schedule_id,
                started_at=current_time,
            )
            schedule.last_queued_at = current_time
            schedule.metadata_json = {}
            summary["schedules_queued"] += 1
            summary["runs_queued"] += result["run_count"]
            if schedule.auto_execute:
                summary["auto_execute_run_ids"].extend([run.run_id for run in result["runs"]])
                summary["auto_execute_schedule_ids"].append(schedule.schedule_id)
        except ValueError as exc:
            schedule.metadata_json = {"last_error": str(exc)}
            summary["schedules_failed"] += 1

        schedule.next_run_at = current_time + timedelta(minutes=schedule.interval_minutes)
        schedule.updated_at = current_time

    session.commit()
    return summary


def _load_schedule_target(
    session: Session,
    *,
    suite_id: str,
    model_name: str,
    node_id: str,
) -> tuple[EvalSuite, list[EvalCase]]:
    suite = session.get(EvalSuite, suite_id)
    if suite is None:
        raise ValueError(f"Unknown eval suite '{suite_id}'")

    node = session.get(Node, node_id)
    if node is None:
        raise ValueError(f"Unknown node '{node_id}'")

    placement = session.scalar(
        select(ModelPlacement).where(
            ModelPlacement.node_id == node_id,
            ModelPlacement.model_name == model_name,
            ModelPlacement.available.is_(True),
        )
    )
    if placement is None:
        raise ValueError(f"Model '{model_name}' is not available on node '{node_id}'")

    cases = session.scalars(
        select(EvalCase).where(EvalCase.suite_id == suite_id).order_by(EvalCase.sort_order, EvalCase.name)
    ).all()
    if not cases:
        raise ValueError(f"Eval suite '{suite_id}' has no cases to queue")

    return suite, cases
