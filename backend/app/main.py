from fastapi import FastAPI

from backend.app.api.health import router as health_router
from backend.app.db import engine
from backend.app.models import Base

app = FastAPI(title="Vantage Control Plane")
app.include_router(health_router, prefix="/api")


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
