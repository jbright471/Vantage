from collections.abc import Sequence
from datetime import UTC, datetime

import httpx

from backend.app.services.endpoint_overrides import resolve_local_ollama_base_urls


def _parse_ollama_tags_payload(payload: dict) -> list[dict]:
    rows: list[dict] = []
    for model in payload.get("models", []):
        name = model.get("name")
        if not name:
            continue
        rows.append(
            {
                "name": name,
                "digest": model.get("digest"),
            }
        )
    return rows


def _merge_models(model_groups: Sequence[list[dict]]) -> list[dict]:
    merged: dict[tuple[str, str | None], dict] = {}
    for group in model_groups:
        for model in group:
            key = (model["name"], model.get("digest"))
            merged[key] = model
    return sorted(merged.values(), key=lambda model: model["name"])


def collect_local_snapshot(
    node_id: str,
    base_urls: Sequence[str] | None = None,
    timeout_seconds: float = 5.0,
) -> dict:
    resolved_urls = resolve_local_ollama_base_urls(base_urls)
    model_groups: list[list[dict]] = []
    errors: list[dict] = []

    for base_url in resolved_urls:
        try:
            response = httpx.get(f"{base_url}/api/tags", timeout=timeout_seconds)
            response.raise_for_status()
            model_groups.append(_parse_ollama_tags_payload(response.json()))
        except httpx.HTTPError as exc:
            errors.append({"base_url": base_url, "error": str(exc)})

    ollama_status = "ok" if errors == [] else "error"
    return {
        "node_id": node_id,
        "captured_at": datetime.now(UTC),
        "gpu_json": [],
        "cpu_json": {"usage_percent": 0},
        "memory_json": {"used_mb": 0},
        "ollama_json": {
            "status": ollama_status,
            "base_urls": resolved_urls,
            "models": _merge_models(model_groups),
            "errors": errors,
        },
    }
