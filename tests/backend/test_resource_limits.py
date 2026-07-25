from backend.app.security.resource_limits import (
    acquire_costly_request,
    clear_resource_limit_state,
    is_costly_request,
)


def test_only_llm_execution_routes_are_costly() -> None:
    assert is_costly_request("POST", "/api/evals/runs/run-1/execute") is True
    assert is_costly_request("POST", "/api/evals/attempts/attempt-1/execute") is True
    assert is_costly_request("POST", "/api/evals/assisted-summary") is True
    assert is_costly_request("POST", "/api/models/capability-check") is True
    assert is_costly_request("GET", "/api/evals/suites") is False


def test_costly_request_rate_is_bounded(monkeypatch) -> None:
    clear_resource_limit_state()
    monkeypatch.setenv("VANTAGE_LLM_REQUESTS_PER_MINUTE", "2")
    monkeypatch.setenv("VANTAGE_LLM_MAX_CONCURRENCY", "2")

    first = acquire_costly_request("operator")
    second = acquire_costly_request("operator")
    assert first.lease is not None
    assert second.lease is not None
    first.lease.release()
    second.lease.release()

    rejected = acquire_costly_request("operator")
    assert rejected.lease is None
    assert rejected.reason == "rate"


def test_costly_request_concurrency_is_bounded(monkeypatch) -> None:
    clear_resource_limit_state()
    monkeypatch.setenv("VANTAGE_LLM_REQUESTS_PER_MINUTE", "100")
    monkeypatch.setenv("VANTAGE_LLM_MAX_CONCURRENCY", "1")

    first = acquire_costly_request("operator")
    assert first.lease is not None
    rejected = acquire_costly_request("another-operator")
    assert rejected.lease is None
    assert rejected.reason == "concurrency"
    first.lease.release()
