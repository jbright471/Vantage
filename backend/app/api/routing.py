from fastapi import APIRouter

from backend.app.db import SessionLocal
from backend.app.services.state import get_routing_state

router = APIRouter()


@router.get("/routing")
def list_routing() -> list[dict]:
    with SessionLocal() as session:
        return get_routing_state(session)
