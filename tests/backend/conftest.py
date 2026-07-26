from fastapi.testclient import TestClient
import pytest

from backend.app.security.resource_limits import clear_resource_limit_state


CONTROL_PLANE_TEST_TOKEN = "control-plane-test-token-000000000000000000"
SESSION_SIGNING_TEST_KEY = "session-signing-test-key-000000000000000000"


@pytest.fixture(autouse=True)
def authenticate_control_plane_test_clients(monkeypatch, tmp_path):
    clear_resource_limit_state()
    monkeypatch.setenv("VANTAGE_CONTROL_PLANE_TOKEN", CONTROL_PLANE_TEST_TOKEN)
    monkeypatch.setenv("VANTAGE_SESSION_SIGNING_KEY", SESSION_SIGNING_TEST_KEY)
    monkeypatch.setenv("VANTAGE_LLM_REQUESTS_PER_MINUTE", "1000")
    test_bootstrap = tmp_path / "vantage.test.bootstrap.toml"
    test_bootstrap.write_text(
        """
app_name = "Vantage Test"
agent_auth_token_env = "VANTAGE_AGENT_SHARED_TOKEN"
local_ollama_base_urls = ["http://127.0.0.1:11400"]

[[nodes]]
node_id = "control-plane"
display_name = "Control Plane"
base_url = "http://127.0.0.1:8000"
role = "primary"
enabled = true

[[nodes]]
node_id = "remote-worker"
display_name = "Remote Worker"
base_url = "http://10.0.0.25:9110"
role = "remote"
enabled = true
        """.strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr("backend.app.main.DEFAULT_BOOTSTRAP_CONFIG_PATH", test_bootstrap)
    monkeypatch.setattr("backend.app.api.actions.DEFAULT_BOOTSTRAP_CONFIG_PATH", test_bootstrap)
    original_init = TestClient.__init__

    def authenticated_init(self, *args, **kwargs):
        headers = dict(kwargs.get("headers") or {})
        headers.setdefault("Authorization", f"Bearer {CONTROL_PLANE_TEST_TOKEN}")
        kwargs["headers"] = headers
        return original_init(self, *args, **kwargs)

    monkeypatch.setattr(TestClient, "__init__", authenticated_init)
    yield
    clear_resource_limit_state()
