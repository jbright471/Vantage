from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
import logging
import os
from pathlib import Path

from backend.app.config import BootstrapConfig
from backend.app.db import SessionLocal
from backend.app.services.reports import build_operator_markdown_report


logger = logging.getLogger("vantage.report_scheduler")
REPORT_SCHEDULE_ENABLED_ENV = "VANTAGE_REPORT_SCHEDULE_ENABLED"
REPORT_OUTPUT_DIR_ENV = "VANTAGE_REPORT_OUTPUT_DIR"


def report_scheduler_enabled() -> bool:
    return os.getenv(REPORT_SCHEDULE_ENABLED_ENV, "0").lower() in {"1", "true", "yes", "on"}


def run_scheduled_report_once(session_factory: Callable = SessionLocal) -> Path:
    output_dir = Path(os.getenv(REPORT_OUTPUT_DIR_ENV, "reports")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    output_path = output_dir / f"vantage-operator-report-{timestamp}.md"
    with session_factory() as session:
        report = build_operator_markdown_report(session)
    output_path.write_text(report, encoding="utf-8")
    return output_path


async def report_scheduler_worker(
    stop_event: asyncio.Event,
    config: BootstrapConfig,
    session_factory: Callable = SessionLocal,
) -> None:
    logger.info("report_scheduler_worker_started interval_seconds=%s", config.report_schedule_interval_seconds)

    while not stop_event.is_set():
        try:
            path = await asyncio.to_thread(run_scheduled_report_once, session_factory)
            logger.info("scheduled_report_written path=%s", path)
        except Exception:
            logger.exception("scheduled_report_failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=config.report_schedule_interval_seconds)
        except asyncio.TimeoutError:
            continue

    logger.info("report_scheduler_worker_stopped")


async def stop_report_scheduler_task(task: asyncio.Task[None], stop_event: asyncio.Event) -> None:
    stop_event.set()
    with suppress(asyncio.CancelledError):
        await task
