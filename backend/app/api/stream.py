from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.app.db import SessionLocal
from backend.app.services.events import EventBroker
from backend.app.services.events import serialize_sse
from backend.app.services.runtime import background_polling_enabled
from backend.app.services.state import build_full_state

router = APIRouter()


@router.get("/stream")
async def stream(request: Request) -> StreamingResponse:
    with SessionLocal() as session:
        initial_state = build_full_state(session)

    broker: EventBroker = request.app.state.event_broker

    async def event_generator():
        if not background_polling_enabled():
            yield serialize_sse({"event": "full_state", "data": initial_state})
            return

        async for payload in broker.subscribe(initial_state):
            yield serialize_sse(payload)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
