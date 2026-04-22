from fastapi import APIRouter

from backend.app.db import SessionLocal
from backend.app.services.state import get_warnings_state

router = APIRouter()


@router.get("/warnings")
def list_warnings() -> list[dict]:
    with SessionLocal() as session:
        return get_warnings_state(session)
