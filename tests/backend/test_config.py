from pathlib import Path

from backend.app.config import DEFAULT_BOOTSTRAP_CONFIG_PATH, load_bootstrap_config, resolve_bootstrap_config_path


def test_public_default_starts_with_only_the_local_control_plane() -> None:
    config = load_bootstrap_config(DEFAULT_BOOTSTRAP_CONFIG_PATH)

    assert [node.node_id for node in config.nodes] == ["control-plane"]
    assert config.nodes[0].enabled is True


def test_load_bootstrap_config_reads_nodes(tmp_path: Path) -> None:
    config_path = tmp_path / "vantage.bootstrap.toml"
    config_path.write_text(
        """
app_name = "Vantage"
poll_interval_seconds = 5
stale_after_seconds = 15
unreachable_after_seconds = 30
local_ollama_base_urls = ["http://127.0.0.1:11434", "http://127.0.0.1:11435"]

[[nodes]]
node_id = "control-plane"
display_name = "Control Plane"
base_url = "http://127.0.0.1:9000"
role = "primary"
enabled = true
        """.strip(),
        encoding="utf-8",
    )

    config = load_bootstrap_config(config_path)

    assert config.app_name == "Vantage"
    assert config.poll_interval_seconds == 5
    assert config.local_ollama_base_urls == ["http://127.0.0.1:11434", "http://127.0.0.1:11435"]
    assert config.nodes[0].node_id == "control-plane"
    assert config.nodes[0].role == "primary"


def test_bootstrap_config_path_supports_a_local_runtime_override(monkeypatch, tmp_path: Path) -> None:
    local_config = tmp_path / "vantage.bootstrap.local.toml"
    monkeypatch.setenv("VANTAGE_BOOTSTRAP_CONFIG_PATH", str(local_config))

    assert resolve_bootstrap_config_path() == local_config


def test_remote_agent_is_the_default_non_primary_node_role(tmp_path: Path) -> None:
    config_path = tmp_path / "worker.toml"
    config_path.write_text(
        """
[[nodes]]
node_id = "gpu-worker"
display_name = "GPU Worker"
base_url = "http://192.0.2.20:9110"
enabled = true
        """.strip(),
        encoding="utf-8",
    )

    assert load_bootstrap_config(config_path).nodes[0].role == "remote"
