from agent.app.collectors import get_models, get_runs, resolve_ollama_base_urls, run_capability_check


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_resolve_ollama_base_urls_prefers_env(monkeypatch) -> None:
    monkeypatch.setenv("VANTAGE_AGENT_OLLAMA_BASE_URLS", "http://127.0.0.1:11435, http://127.0.0.1:21435")

    assert resolve_ollama_base_urls() == ["http://127.0.0.1:11435", "http://127.0.0.1:21435"]


def test_get_models_reads_ollama_tags_over_http(monkeypatch) -> None:
    def fake_get(url: str, timeout: float) -> FakeResponse:
        assert timeout == 5.0
        if url == "http://127.0.0.1:11435/api/tags":
            return FakeResponse({"models": [{"name": "qwen3.5:27b", "digest": "sha256:111"}]})
        raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr("agent.app.collectors.httpx.get", fake_get)
    monkeypatch.delenv("VANTAGE_AGENT_OLLAMA_BASE_URLS", raising=False)

    models = get_models()

    assert models == [{"model_name": "qwen3.5:27b", "model_digest": "sha256:111", "available": True}]


def test_get_runs_reports_active_loaded_models(monkeypatch) -> None:
    def fake_get(url: str, timeout: float) -> FakeResponse:
        assert timeout == 5.0
        if url == "http://127.0.0.1:11435/api/ps":
            return FakeResponse({"models": [{"name": "gemma4:e4b", "digest": "sha256:aaa", "size_vram": 100}]})
        raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr("agent.app.collectors.httpx.get", fake_get)
    monkeypatch.delenv("VANTAGE_AGENT_OLLAMA_BASE_URLS", raising=False)

    runs = get_runs()

    assert runs[0]["detail_type"] == "ollama_loaded_model"
    assert runs[0]["model_name"] == "gemma4:e4b"


def test_run_capability_check_records_recent_success(monkeypatch) -> None:
    class FakePostResponse(FakeResponse):
        def json(self) -> dict:
            return {"response": '{"mode":"ok","json":"yes","notes":"healthy"}'}

    monkeypatch.setattr("agent.app.collectors.httpx.post", lambda *args, **kwargs: FakePostResponse({}))
    monkeypatch.delenv("VANTAGE_AGENT_OLLAMA_BASE_URLS", raising=False)

    run = run_capability_check("gemma4:e4b")

    assert run["status"] == "success"
    assert run["detail_type"] == "capability_check"
