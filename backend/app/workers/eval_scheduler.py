import asyncio
from collections.abc import Callable
from contextlib import suppress
import logging

from backend.app.config import BootstrapConfig
from backend.app.db import SessionLocal
from backend.app.services.eval_schedules import queue_due_eval_schedules
from backend.app.models import EvalSchedule, Node, Run, WarningRecord
from backend.app.services.evals import execute_eval_run
from backend.app.services.events import EventBroker
from backend.app.services.state import build_full_state

logger = logging.getLogger("vantage.eval_scheduler")


def run_due_eval_schedules(
    config: BootstrapConfig,
    broker: EventBroker | None = None,
    session_factory: Callable = SessionLocal,
) -> dict[str, int]:
    with session_factory() as session:
        summary = queue_due_eval_schedules(session)

    executed_count = 0
    execution_error_count = 0
    failed_run_count = 0
    schedule_results: dict[str, dict[str, object]] = {}
    for run_id in summary.get("auto_execute_run_ids", []):
        with session_factory() as session:
            run = session.get(Run, run_id)
            if run is None:
                execution_error_count += 1
                continue
            node = run.node_id and session.get(Node, run.node_id)
            if node is None:
                execution_error_count += 1
                continue
            updated = execute_eval_run(session, run, node=node, config=config)
            executed_count += 1
            schedule_id = updated.metadata_json.get("schedule_id") if isinstance(updated.metadata_json, dict) else None
            if isinstance(schedule_id, str):
                result = schedule_results.setdefault(
                    schedule_id,
                    {"run_ids": [], "failed_run_ids": [], "node_id": updated.node_id, "model_name": updated.model_name},
                )
                result["run_ids"].append(updated.run_id)
                if updated.status == "failed":
                    result["failed_run_ids"].append(updated.run_id)
                    failed_run_count += 1

    if summary.get("auto_execute_run_ids"):
        with session_factory() as session:
            for schedule_id in summary.get("auto_execute_schedule_ids", []):
                schedule = session.get(EvalSchedule, schedule_id)
                result = schedule_results.get(schedule_id, {"run_ids": [], "failed_run_ids": []})
                run_ids = list(result["run_ids"])
                failed_run_ids = list(result["failed_run_ids"])
                if schedule is not None:
                    schedule.metadata_json = {
                        **(schedule.metadata_json or {}),
                        "last_auto_execute": {
                            "runs_executed": len(run_ids),
                            "runs_failed": len(failed_run_ids),
                            "run_ids": run_ids,
                            "failed_run_ids": failed_run_ids,
                        },
                    }
                    _sync_eval_schedule_warning(session, schedule, run_ids=run_ids, failed_run_ids=failed_run_ids)
            session.commit()

    return {
        "schedules_checked": int(summary["schedules_checked"]),
        "schedules_queued": int(summary["schedules_queued"]),
        "runs_queued": int(summary["runs_queued"]),
        "schedules_failed": int(summary["schedules_failed"]),
        "runs_executed": executed_count,
        "runs_failed": failed_run_count,
        "runs_execution_failed": execution_error_count,
    }


def _sync_eval_schedule_warning(
    session,
    schedule: EvalSchedule,
    *,
    run_ids: list[str],
    failed_run_ids: list[str],
) -> None:
    from datetime import UTC, datetime

    warning_id = f"eval-schedule-failure:{schedule.schedule_id}"
    now = datetime.now(UTC)
    warning = session.get(WarningRecord, warning_id)

    if failed_run_ids:
        summary = (
            f"Scheduled eval for {schedule.model_name} on {schedule.node_id} failed "
            f"{len(failed_run_ids)} of {len(run_ids)} run{'' if len(run_ids) == 1 else 's'}"
        )
        metadata_json = {
            "schedule_id": schedule.schedule_id,
            "suite_id": schedule.suite_id,
            "model_name": schedule.model_name,
            "node_id": schedule.node_id,
            "run_ids": run_ids,
            "failed_run_ids": failed_run_ids,
            "failed_count": len(failed_run_ids),
            "run_count": len(run_ids),
        }
        if warning is None:
            session.add(
                WarningRecord(
                    warning_id=warning_id,
                    warning_type="eval_schedule_failure",
                    severity="warning",
                    node_id=schedule.node_id,
                    first_seen_at=now,
                    last_seen_at=now,
                    status="active",
                    summary=summary,
                    metadata_json=metadata_json,
                )
            )
        else:
            warning.last_seen_at = now
            warning.status = "active"
            warning.severity = "warning"
            warning.summary = summary
            warning.metadata_json = metadata_json
        return

    if warning is not None and warning.status in {"active", "acknowledged"}:
        warning.status = "resolved"
        warning.last_seen_at = now
        warning.metadata_json = {
            **(warning.metadata_json or {}),
            "resolved_by_run_ids": run_ids,
            "resolved_at": now.isoformat(),
        }


async def eval_scheduler_worker(
    stop_event: asyncio.Event,
    config: BootstrapConfig,
    broker: EventBroker | None = None,
    session_factory: Callable = SessionLocal,
) -> None:
    logger.info("eval_scheduler_worker_started interval_seconds=%s", config.eval_schedule_interval_seconds)

    while not stop_event.is_set():
        try:
            summary = await asyncio.to_thread(run_due_eval_schedules, config, broker, session_factory)
            if summary["runs_queued"] or summary["schedules_failed"]:
                logger.info(
                    "eval_schedules_checked schedules_queued=%s runs_queued=%s schedules_failed=%s",
                    summary["schedules_queued"],
                    summary["runs_queued"],
                    summary["schedules_failed"],
                )
            if broker is not None and summary["runs_queued"] > 0:
                with session_factory() as session:
                    await broker.publish("full_state", build_full_state(session, config=config))
        except Exception:
            logger.exception("eval_scheduler_failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=config.eval_schedule_interval_seconds)
        except asyncio.TimeoutError:
            continue

    logger.info("eval_scheduler_worker_stopped")


async def stop_eval_scheduler_task(task: asyncio.Task[None], stop_event: asyncio.Event) -> None:
    stop_event.set()
    with suppress(asyncio.CancelledError):
        await task
