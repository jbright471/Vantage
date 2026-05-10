from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class Collector(Protocol):
    name: str
    runtime: str

    def describe(self) -> dict:
        ...


@dataclass(frozen=True)
class CollectorDescriptor:
    name: str
    runtime: str
    description: str
    config_keys: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    endpoints: tuple[str, ...] = ()
    auth_modes: tuple[str, ...] = ()
    built_in: bool = True
    status: str = "available"

    def describe(self) -> dict:
        return {
            "name": self.name,
            "runtime": self.runtime,
            "description": self.description,
            "config_keys": list(self.config_keys),
            "capabilities": list(self.capabilities),
            "endpoints": list(self.endpoints),
            "auth_modes": list(self.auth_modes),
            "built_in": self.built_in,
            "status": self.status,
        }


class CollectorRegistry:
    def __init__(self) -> None:
        self._collectors: dict[str, Collector] = {}

    def register(self, collector: Collector) -> None:
        self._collectors[collector.name] = collector

    def get(self, name: str) -> Collector | None:
        return self._collectors.get(name)

    def list_collectors(self) -> list[dict]:
        return [collector.describe() for collector in self._collectors.values()]


default_collector_registry = CollectorRegistry()
default_collector_registry.register(
    CollectorDescriptor(
        name="ollama",
        runtime="local_or_agent",
        description="Built-in Ollama model, loaded-model, and capability telemetry collector.",
        config_keys=("local_ollama_base_urls", "VANTAGE_AGENT_OLLAMA_BASE_URLS"),
        capabilities=("models", "loaded_models", "capability_checks", "runs"),
        endpoints=("/api/models", "/api/ps", "/api/generate", "/api/runs"),
        auth_modes=("none", "agent_bearer", "agent_hmac"),
    )
)
