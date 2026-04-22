from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.app.db import SessionLocal
from backend.app.services.events import serialize_sse
from backend.app.services.state import build_full_state

router = APIRouter()


@router.get("/stream")
async def stream() -> StreamingResponse:
    with SessionLocal() as session:
        initial_state = build_full_state(session)

    def event_generator():
        yield serialize_sse({"event": "full_state", "data": initial_state})

    return StreamingResponse(event_generator(), media_type="text/event-stream")
