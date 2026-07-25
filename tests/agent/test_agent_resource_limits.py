from agent.app.resource_limits import acquire_agent_operation, clear_agent_resource_limit_state


def test_agent_llm_operations_have_rate_and_concurrency_bounds(monkeypatch) -> None:
    clear_agent_resource_limit_state()
    monkeypatch.setenv("VANTAGE_AGENT_LLM_REQUESTS_PER_MINUTE", "2")
    monkeypatch.setenv("VANTAGE_AGENT_LLM_MAX_CONCURRENCY", "1")

    first = acquire_agent_operation("control-plane")
    assert first.lease is not None

    concurrent = acquire_agent_operation("other-control-plane")
    assert concurrent.reason == "concurrency"
    first.lease.release()

    second = acquire_agent_operation("control-plane")
    assert second.lease is not None
    second.lease.release()

    rate_limited = acquire_agent_operation("control-plane")
    assert rate_limited.reason == "rate"
