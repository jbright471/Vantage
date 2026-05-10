import asyncio
import hashlib
import hmac

from backend.app.collectors.remote import BastetClient


def test_bastet_client_sends_bearer_token(monkeypatch) -> None:
    captured_headers = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"status": "ok"}

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 5.0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def get(self, url: str, *, headers: dict | None = None) -> FakeResponse:
            captured_headers.update(headers or {})
            return FakeResponse()

    monkeypatch.setattr("backend.app.collectors.remote.httpx.AsyncClient", FakeAsyncClient)

    payload = asyncio.run(BastetClient("http://bastet:9110", auth_token="secret-token").fetch_health())

    assert payload == {"status": "ok"}
    assert captured_headers["Authorization"] == "Bearer secret-token"


def test_bastet_client_sends_hmac_signature(monkeypatch) -> None:
    captured_headers = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"status": "ok"}

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 5.0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def get(self, url: str, *, headers: dict | None = None) -> FakeResponse:
            captured_headers.update(headers or {})
            return FakeResponse()

    monkeypatch.setattr("backend.app.collectors.remote.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr("backend.app.collectors.remote.time.time", lambda: 1770000000)
    monkeypatch.setattr("backend.app.collectors.remote.secrets.token_urlsafe", lambda length: "nonce-1")

    payload = asyncio.run(
        BastetClient("http://bastet:9110", auth_token="secret-token", auth_mode="hmac", key_id="agent-key-1").fetch_health()
    )

    body_hash = hashlib.sha256(b"").hexdigest()
    expected_message = "\n".join(["GET", "/health", "1770000000", "nonce-1", body_hash])
    expected_signature = hmac.new(b"secret-token", expected_message.encode("utf-8"), hashlib.sha256).hexdigest()
    assert payload == {"status": "ok"}
    assert captured_headers["X-Vantage-Timestamp"] == "1770000000"
    assert captured_headers["X-Vantage-Nonce"] == "nonce-1"
    assert captured_headers["X-Vantage-Key-Id"] == "agent-key-1"
    assert captured_headers["X-Vantage-Signature"] == expected_signature
