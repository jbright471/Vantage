import asyncio
from collections.abc import Callable
from contextlib import suppress
import logging

from backend.app.config import BootstrapConfig
from backend.app.db import SessionLocal
from backend.app.services.pruning import PruneSummary, prune_snapshots

logger = logging.getLogger("vantage.pruner")


def run_snapshot_pruning(config: BootstrapConfig, session_factory: Callable = SessionLocal) -> PruneSummary:
    with session_factory() as session:
        return prune_snapshots(
            session,
            retention_hours=config.snapshot_retention_hours,
            max_per_node=config.snapshot_max_per_node,
            min_per_node=config.snapshot_min_per_node,
        )


async def snapshot_pruning_worker(
    stop_event: asyncio.Event,
    config: BootstrapConfig,
    session_factory: Callable = SessionLocal,
) -> None:
    logger.info("snapshot_pruning_worker_started interval_seconds=%s", config.snapshot_prune_interval_seconds)

    while not stop_event.is_set():
        try:
            summary = await asyncio.to_thread(run_snapshot_pruning, config, session_factory)
            if summary.total_deleted:
                logger.info(
                    "snapshot_pruned deleted_by_age=%s deleted_by_count=%s",
                    summary.deleted_by_age,
                    summary.deleted_by_count,
                )
        except Exception:
            logger.exception("snapshot_pruning_failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=config.snapshot_prune_interval_seconds)
        except asyncio.TimeoutError:
            continue

    logger.info("snapshot_pruning_worker_stopped")


async def stop_pruning_task(task: asyncio.Task[None], stop_event: asyncio.Event) -> None:
    stop_event.set()
    with suppress(asyncio.CancelledError):
        await task
