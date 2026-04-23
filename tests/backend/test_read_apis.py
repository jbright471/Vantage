from fastapi.testclient import TestClient

from backend.app.main import app


def test_nodes_runs_models_routing_and_warnings_endpoints_exist() -> None:
    with TestClient(app) as client:
        nodes = client.get("/api/nodes")
        runs = client.get("/api/runs")
        models = client.get("/api/models")
        routing = client.get("/api/routing")
        warnings = client.get("/api/warnings")

        assert nodes.status_code == 200
        assert runs.status_code == 200
        assert models.status_code == 200
        assert routing.status_code == 200
        assert warnings.status_code == 200

        jedi = next(node for node in nodes.json() if node["node_id"] == "jedi")

        assert jedi["base_url"] == "http://127.0.0.1:8000"
        assert "gpu_stats" in jedi
        assert "model_count" in jedi
        assert "ollama_status" in jedi
        assert isinstance(runs.json(), list)
        assert isinstance(models.json(), list)
        assert isinstance(routing.json(), list)
        assert isinstance(warnings.json(), list)
        assert any(rule["rule_id"] == "interactive-default" for rule in routing.json())
