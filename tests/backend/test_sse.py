import json

from fastapi.testclient import TestClient

from backend.app.main import app


def test_stream_emits_full_state_event_first() -> None:
    with TestClient(app) as client:
        with client.stream("GET", "/api/stream") as response:
            lines = response.iter_lines()
            first = next(lines)
            second = next(lines)

    assert first == "event: full_state"
    payload = json.loads(second.removeprefix("data: "))
    assert set(payload) == {"nodes", "runs", "models", "routing", "warnings"}
