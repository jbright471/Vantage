from fastapi import APIRouter

from backend.app.db import SessionLocal
from backend.app.services.state import get_models_state

router = APIRouter()


@router.get("/models")
def list_models() -> list[dict]:
    with SessionLocal() as session:
        return get_models_state(session)
