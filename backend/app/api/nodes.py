from fastapi import APIRouter

from backend.app.db import SessionLocal
from backend.app.services.state import get_nodes_state

router = APIRouter()


@router.get("/nodes")
def list_nodes() -> list[dict]:
    with SessionLocal() as session:
        return get_nodes_state(session)
