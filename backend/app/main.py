import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api.actions import router as actions_router
from backend.app.api.docs import router as docs_router
from backend.app.api.evals import router as evals_router
from backend.app.api.health import router as health_router
from backend.app.api.models import router as models_router
from backend.app.api.nodes import router as nodes_router
from backend.app.api.routing import router as routing_router
from backend.app.api.runs import router as runs_router
from backend.app.api.stream import router as stream_router
from backend.app.api.warnings import router as warnings_router
from backend.app.config import DEFAULT_BOOTSTRAP_CONFIG_PATH, load_bootstrap_config
from backend.app.db import SessionLocal, engine, ensure_runtime_schema
from backend.app.models import Base
from backend.app.services.bootstrap import seed_nodes_from_config, seed_routing_from_config
from backend.app.services.events import EventBroker
from backend.app.services.runtime import background_polling_enabled, poll_forever, run_poll_cycle, stop_polling_task
from backend.app.workers.eval_scheduler import eval_scheduler_worker, stop_eval_scheduler_task
from backend.app.workers.pruner import snapshot_pruning_worker, stop_pruning_task
from backend.app.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema()
    config = load_bootstrap_config(DEFAULT_BOOTSTRAP_CONFIG_PATH)
    app.state.config = config
    broker = EventBroker()
    app.state.event_broker = broker

    with SessionLocal() as session:
        seed_nodes_from_config(session, config)
        seed_routing_from_config(session, config)

    poller_task: asyncio.Task[None] | None = None
    pruner_task: asyncio.Task[None] | None = None
    eval_scheduler_task: asyncio.Task[None] | None = None
    if background_polling_enabled():
        await run_poll_cycle(config, broker=broker)
        stop_event = asyncio.Event()
        app.state.poller_stop_event = stop_event
        poller_task = asyncio.create_task(poll_forever(stop_event, config, broker))
        app.state.poller_task = poller_task
        pruner_stop_event = asyncio.Event()
        app.state.pruner_stop_event = pruner_stop_event
        pruner_task = asyncio.create_task(snapshot_pruning_worker(pruner_stop_event, config))
        app.state.pruner_task = pruner_task
        eval_scheduler_stop_event = asyncio.Event()
        app.state.eval_scheduler_stop_event = eval_scheduler_stop_event
        eval_scheduler_task = asyncio.create_task(eval_scheduler_worker(eval_scheduler_stop_event, config, broker))
        app.state.eval_scheduler_task = eval_scheduler_task

    try:
        yield
    finally:
        if eval_scheduler_task is not None:
            await stop_eval_scheduler_task(eval_scheduler_task, app.state.eval_scheduler_stop_event)
        if pruner_task is not None:
            await stop_pruning_task(pruner_task, app.state.pruner_stop_event)
        if poller_task is not None:
            app.state.poller_stop_event.set()
            await stop_polling_task(poller_task)


app = FastAPI(title="Vantage Control Plane", lifespan=lifespan)
app.include_router(health_router, prefix="/api")
app.include_router(actions_router, prefix="/api")
app.include_router(docs_router, prefix="/api")
app.include_router(evals_router, prefix="/api")
app.include_router(nodes_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
app.include_router(models_router, prefix="/api")
app.include_router(routing_router, prefix="/api")
app.include_router(warnings_router, prefix="/api")
app.include_router(stream_router, prefix="/api")
