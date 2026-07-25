from fastapi.testclient import TestClient
import pytest

from backend.app.security.resource_limits import clear_resource_limit_state


CONTROL_PLANE_TEST_TOKEN = "control-plane-test-token-000000000000000000"
SESSION_SIGNING_TEST_KEY = "session-signing-test-key-000000000000000000"


@pytest.fixture(autouse=True)
def authenticate_control_plane_test_clients(monkeypatch):
    clear_resource_limit_state()
    monkeypatch.setenv("VANTAGE_CONTROL_PLANE_TOKEN", CONTROL_PLANE_TEST_TOKEN)
    monkeypatch.setenv("VANTAGE_SESSION_SIGNING_KEY", SESSION_SIGNING_TEST_KEY)
    monkeypatch.setenv("VANTAGE_LLM_REQUESTS_PER_MINUTE", "1000")
    original_init = TestClient.__init__

    def authenticated_init(self, *args, **kwargs):
        headers = dict(kwargs.get("headers") or {})
        headers.setdefault("Authorization", f"Bearer {CONTROL_PLANE_TEST_TOKEN}")
        kwargs["headers"] = headers
        return original_init(self, *args, **kwargs)

    monkeypatch.setattr(TestClient, "__init__", authenticated_init)
    yield
    clear_resource_limit_state()
