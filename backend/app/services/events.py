import asyncio
import json
from collections.abc import AsyncIterator


class EventBroker:
    def __init__(self) -> None:
        self._queues: list[asyncio.Queue[dict]] = []

    async def subscribe(self, initial_state: dict) -> AsyncIterator[dict]:
        queue: asyncio.Queue[dict] = asyncio.Queue()
        self._queues.append(queue)
        try:
            yield {"event": "full_state", "data": initial_state}
            while True:
                payload = await queue.get()
                yield payload
        finally:
            self._queues.remove(queue)

    async def publish(self, event: str, data: dict) -> None:
        for queue in list(self._queues):
            await queue.put({"event": event, "data": data})


def serialize_sse(payload: dict) -> str:
    return f"event: {payload['event']}\ndata: {json.dumps(payload['data'])}\n\n"
