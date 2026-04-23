import asyncio

from backend.app.collectors.remote import BastetClient


def test_bastet_client_sends_bearer_token(monkeypatch) -> None:
    captured_headers = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"status": "ok"}

    class FakeAsyncClient:
        def __init__(self, *, timeout: float, headers: dict | None = None) -> None:
            captured_headers.update(headers or {})

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def get(self, url: str) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("backend.app.collectors.remote.httpx.AsyncClient", FakeAsyncClient)

    payload = asyncio.run(BastetClient("http://bastet:9110", auth_token="secret-token").fetch_health())

    assert payload == {"status": "ok"}
    assert captured_headers["Authorization"] == "Bearer secret-token"
