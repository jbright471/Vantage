from agent.app.collectors import get_models, get_runs, resolve_ollama_base_urls, run_capability_check, run_eval_attempt


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
        if url == "http://127.0.0.1:11434/api/tags":
            return FakeResponse({"models": [{"name": "qwen3.5:27b", "digest": "sha256:111"}]})
        raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr("agent.app.collectors.httpx.get", fake_get)
    monkeypatch.delenv("VANTAGE_AGENT_OLLAMA_BASE_URLS", raising=False)

    models = get_models()

    assert models == [{"model_name": "qwen3.5:27b", "model_digest": "sha256:111", "available": True}]


def test_get_runs_reports_active_loaded_models(monkeypatch) -> None:
    def fake_get(url: str, timeout: float) -> FakeResponse:
        assert timeout == 5.0
        if url == "http://127.0.0.1:11434/api/ps":
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
            return {"response": '{"mode":"inference","json":true,"notes":"ok"}'}

    captured = {}

    def fake_post(*args, **kwargs):
        captured["payload"] = kwargs["json"]
        return FakePostResponse({})

    monkeypatch.setattr("agent.app.collectors.httpx.post", fake_post)
    monkeypatch.delenv("VANTAGE_AGENT_OLLAMA_BASE_URLS", raising=False)

    run = run_capability_check("gemma4:e4b")

    assert run["status"] == "success"
    assert run["detail_type"] == "capability_check"
    assert run["metadata_json"]["response_json"] == {"mode": "inference", "json": True, "notes": "ok"}
    assert captured["payload"]["format"] == "json"


def test_run_capability_check_rejects_non_deterministic_response(monkeypatch) -> None:
    class FakePostResponse(FakeResponse):
        def json(self) -> dict:
            return {"response": '{"mode":"offline","json":true,"notes":"invented"}'}

    monkeypatch.setattr("agent.app.collectors.httpx.post", lambda *args, **kwargs: FakePostResponse({}))
    monkeypatch.delenv("VANTAGE_AGENT_OLLAMA_BASE_URLS", raising=False)

    run = run_capability_check("gemma4:e4b")

    assert run["status"] == "failed"
    assert "deterministic handshake" in run["metadata_json"]["errors"][0]["error"]


def test_run_eval_attempt_records_response_and_score(monkeypatch) -> None:
    class FakePostResponse(FakeResponse):
        def json(self) -> dict:
            return {"response": '{"answer":42,"notes":"ok"}'}

    captured = {}

    def fake_post(*args, **kwargs):
        captured["payload"] = kwargs["json"]
        return FakePostResponse({})

    monkeypatch.setattr("agent.app.collectors.httpx.post", fake_post)
    monkeypatch.delenv("VANTAGE_AGENT_OLLAMA_BASE_URLS", raising=False)

    run = run_eval_attempt("gemma4:e4b", prompt="Return answer", expected_json={"answer": 42})

    assert run["status"] == "success"
    assert run["detail_type"] == "eval_attempt"
    assert run["metadata_json"]["score"]["passed"] is True
    assert captured["payload"]["options"]["num_predict"] == 512


def test_run_eval_attempt_rejects_oversized_model_response(monkeypatch) -> None:
    class FakePostResponse(FakeResponse):
        def json(self) -> dict:
            return {"response": "x" * 2049}

    monkeypatch.setattr("agent.app.collectors.httpx.post", lambda *args, **kwargs: FakePostResponse({}))
    monkeypatch.setenv("VANTAGE_AGENT_OLLAMA_BASE_URLS", "http://127.0.0.1:11400")
    monkeypatch.setenv("VANTAGE_LLM_MAX_RESPONSE_CHARS", "2048")

    run = run_eval_attempt("gemma4:e4b", prompt="Return answer")

    assert run["status"] == "failed"
    assert "response_text" not in run["metadata_json"]
    assert "configured size limit" in run["metadata_json"]["errors"][0]["error"]
