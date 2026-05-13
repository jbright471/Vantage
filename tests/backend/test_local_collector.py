import httpx

from backend.app.collectors.local import collect_local_snapshot, resolve_local_ollama_base_urls


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_resolve_local_ollama_base_urls_prefers_env(monkeypatch) -> None:
    monkeypatch.setenv("VANTAGE_LOCAL_OLLAMA_BASE_URLS", "http://host.docker.internal:11434, http://host.docker.internal:11435")

    resolved = resolve_local_ollama_base_urls(["http://127.0.0.1:11434"])

    assert resolved == ["http://host.docker.internal:11434", "http://host.docker.internal:11435"]


def test_collect_local_snapshot_reads_models_from_http(monkeypatch) -> None:
    def fake_get(url: str, timeout: float) -> FakeResponse:
        assert timeout == 5.0
        if url == "http://127.0.0.1:11434/api/tags":
            return FakeResponse({"models": [{"name": "qwen3.5:27b", "digest": "sha256:111"}]})
        if url == "http://127.0.0.1:11435/api/tags":
            return FakeResponse({"models": [{"name": "gemma3:12b", "digest": "sha256:222"}]})
        raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr("backend.app.collectors.local.httpx.get", fake_get)

    snapshot = collect_local_snapshot(
        node_id="control-plane",
        base_urls=["http://127.0.0.1:11434", "http://127.0.0.1:11435"],
    )

    assert snapshot["ollama_json"]["status"] == "ok"
    assert snapshot["ollama_json"]["models"] == [
        {"name": "gemma3:12b", "digest": "sha256:222"},
        {"name": "qwen3.5:27b", "digest": "sha256:111"},
    ]


def test_collect_local_snapshot_marks_partial_failure(monkeypatch) -> None:
    def fake_get(url: str, timeout: float) -> FakeResponse:
        if url == "http://127.0.0.1:11434/api/tags":
            return FakeResponse({"models": [{"name": "qwen3.5:27b", "digest": "sha256:111"}]})
        raise httpx.ConnectError("offline")

    monkeypatch.setattr("backend.app.collectors.local.httpx.get", fake_get)

    snapshot = collect_local_snapshot(
        node_id="control-plane",
        base_urls=["http://127.0.0.1:11434", "http://127.0.0.1:11435"],
    )

    assert snapshot["ollama_json"]["status"] == "error"
    assert snapshot["ollama_json"]["models"] == [{"name": "qwen3.5:27b", "digest": "sha256:111"}]
    assert snapshot["ollama_json"]["errors"][0]["base_url"] == "http://127.0.0.1:11435"
