from pathlib import Path

from backend.app.config import load_bootstrap_config


def test_load_bootstrap_config_reads_nodes(tmp_path: Path) -> None:
    config_path = tmp_path / "vantage.bootstrap.toml"
    config_path.write_text(
        """
app_name = "Vantage"
poll_interval_seconds = 5
stale_after_seconds = 15
unreachable_after_seconds = 30

[[nodes]]
node_id = "jedi"
display_name = "Jedi"
base_url = "http://127.0.0.1:9000"
role = "primary"
enabled = true
        """.strip(),
        encoding="utf-8",
    )

    config = load_bootstrap_config(config_path)

    assert config.app_name == "Vantage"
    assert config.poll_interval_seconds == 5
    assert config.nodes[0].node_id == "jedi"
    assert config.nodes[0].role == "primary"
