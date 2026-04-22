from collections.abc import Sequence
import os
import subprocess

import httpx


DEFAULT_AGENT_OLLAMA_BASE_URLS = ("http://127.0.0.1:11435",)
AGENT_OLLAMA_BASE_URLS_ENV = "VANTAGE_AGENT_OLLAMA_BASE_URLS"


def resolve_ollama_base_urls() -> list[str]:
    raw_urls = os.getenv(AGENT_OLLAMA_BASE_URLS_ENV)
    if raw_urls:
        candidates = [part.strip() for part in raw_urls.split(",")]
    else:
        candidates = list(DEFAULT_AGENT_OLLAMA_BASE_URLS)

    return [candidate.rstrip("/") for candidate in candidates if candidate.strip()]


def _parse_ollama_tags_payload(payload: dict) -> list[dict]:
    rows: list[dict] = []
    for model in payload.get("models", []):
        model_name = model.get("name")
        if not model_name:
            continue
        rows.append(
            {
                "model_name": model_name,
                "model_digest": model.get("digest"),
                "available": True,
            }
        )
    return rows


def _merge_models(model_groups: Sequence[list[dict]]) -> list[dict]:
    merged: dict[tuple[str, str | None], dict] = {}
    for group in model_groups:
        for model in group:
            key = (model["model_name"], model.get("model_digest"))
            merged[key] = model
    return sorted(merged.values(), key=lambda model: model["model_name"])


def get_health() -> dict:
    return {"status": "ok", "node_id": "bastet"}


def get_gpu_stats() -> list[dict]:
    result = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,temperature.gpu",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    rows = []
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        name, memory_total_mb, temperature_c = [part.strip() for part in line.split(",")]
        rows.append(
            {
                "name": name,
                "memory_total_mb": int(memory_total_mb),
                "temperature_c": int(temperature_c),
            }
        )
    return rows


def get_models() -> list[dict]:
    model_groups: list[list[dict]] = []
    for base_url in resolve_ollama_base_urls():
        response = httpx.get(f"{base_url}/api/tags", timeout=5.0)
        response.raise_for_status()
        model_groups.append(_parse_ollama_tags_payload(response.json()))
    return _merge_models(model_groups)


def get_runs() -> list[dict]:
    return []
