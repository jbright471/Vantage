import asyncio

from fastapi.testclient import TestClient

from agent.app.auth import clear_replay_cache
from agent.app.main import app as agent_app
from backend.app.collectors.remote import RemoteAgentClient


TEST_AGENT_TOKEN = "integration-agent-token-00000000000000000000"


def test_control_plane_transport_reaches_real_agent_contract_with_hmac(monkeypatch) -> None:
    clear_replay_cache()
    monkeypatch.setenv("VANTAGE_AGENT_SHARED_TOKEN", TEST_AGENT_TOKEN)
    monkeypatch.setenv("VANTAGE_AGENT_AUTH_MODE", "hmac")
    monkeypatch.setenv("VANTAGE_AGENT_KEY_ID", "worker-alpha-v1")
    monkeypatch.setenv("VANTAGE_AGENT_NODE_ID", "worker-alpha")
    monkeypatch.setattr(
        "agent.app.collectors.run_capability_check",
        lambda model_name, prompt=None: {
            "run_id": "signed-capability-run",
            "source_type": "inference",
            "detail_type": "capability_check",
            "source_id": f"capability-check:worker-alpha:{model_name}",
            "node_id": "worker-alpha",
            "model_name": model_name,
            "action_type": "infer",
            "status": "success",
            "started_at": "2026-07-25T20:00:00+00:00",
            "ended_at": "2026-07-25T20:00:01+00:00",
            "duration_ms": 1000,
            "summary": "Signed capability check passed",
            "metadata_json": {"response_text": '{"ok":true}'},
        },
    )

    with TestClient(agent_app) as contract_client:
        class AgentAsyncClientBridge:
            def __init__(self, *, timeout: float) -> None:
                assert timeout == 5.0

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return None

            async def get(self, url: str, *, headers: dict[str, str]):
                return contract_client.get("/health", headers=headers)

        class AgentClientBridge:
            def __init__(self, *, timeout: float) -> None:
                assert timeout == 60.0

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return None

            def post(self, url: str, *, content: bytes, headers: dict[str, str]):
                return contract_client.post("/capability-check", content=content, headers=headers)

        monkeypatch.setattr("backend.app.collectors.remote.httpx.AsyncClient", AgentAsyncClientBridge)
        monkeypatch.setattr("backend.app.collectors.remote.httpx.Client", AgentClientBridge)
        client = RemoteAgentClient(
            "http://worker-alpha:9110",
            auth_token=TEST_AGENT_TOKEN,
            auth_mode="hmac",
            key_id="worker-alpha-v1",
        )

        health = asyncio.run(client.fetch_health())
        capability = client.post_json(
            "/capability-check",
            {"model_name": "qwen:test", "prompt": "Return JSON"},
            timeout=60.0,
        )

    assert health == {"status": "ok", "node_id": "worker-alpha"}
    assert capability["status"] == "success"
    assert capability["node_id"] == "worker-alpha"
