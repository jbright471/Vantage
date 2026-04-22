from fastapi import APIRouter

from backend.app.db import SessionLocal
from backend.app.services.state import get_runs_state

router = APIRouter()


@router.get("/runs")
def list_runs() -> list[dict]:
    with SessionLocal() as session:
        return get_runs_state(session)
