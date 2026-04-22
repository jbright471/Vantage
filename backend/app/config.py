from pathlib import Path
import tomllib

from pydantic import BaseModel, Field

DEFAULT_BOOTSTRAP_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "vantage.bootstrap.toml"


class BootstrapNode(BaseModel):
    node_id: str
    display_name: str
    base_url: str
    role: str = "worker"
    enabled: bool = True


class BootstrapConfig(BaseModel):
    app_name: str = "Vantage"
    poll_interval_seconds: int = 5
    stale_after_seconds: int = 15
    unreachable_after_seconds: int = 30
    snapshot_retention_hours: int = 24
    run_timeout_seconds: int = 300
    abandoned_after_seconds: int = 900
    idempotency_dedupe_seconds: int = 30
    nodes: list[BootstrapNode] = Field(default_factory=list)


def load_bootstrap_config(path: str | Path) -> BootstrapConfig:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    return BootstrapConfig.model_validate(data)
