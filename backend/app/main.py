from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api.actions import router as actions_router
from backend.app.api.health import router as health_router
from backend.app.api.models import router as models_router
from backend.app.api.nodes import router as nodes_router
from backend.app.api.routing import router as routing_router
from backend.app.api.runs import router as runs_router
from backend.app.api.stream import router as stream_router
from backend.app.api.warnings import router as warnings_router
from backend.app.config import DEFAULT_BOOTSTRAP_CONFIG_PATH, load_bootstrap_config
from backend.app.db import SessionLocal, engine
from backend.app.models import Base
from backend.app.services.bootstrap import seed_nodes_from_config


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    config = load_bootstrap_config(DEFAULT_BOOTSTRAP_CONFIG_PATH)
    with SessionLocal() as session:
        seed_nodes_from_config(session, config)
    yield


app = FastAPI(title="Vantage Control Plane", lifespan=lifespan)
app.include_router(health_router, prefix="/api")
app.include_router(actions_router, prefix="/api")
app.include_router(nodes_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
app.include_router(models_router, prefix="/api")
app.include_router(routing_router, prefix="/api")
app.include_router(warnings_router, prefix="/api")
app.include_router(stream_router, prefix="/api")
