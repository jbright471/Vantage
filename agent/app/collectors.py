from collections.abc import Sequence
from collections import deque
from datetime import UTC, datetime
import hashlib
import os
import subprocess
from uuid import uuid4

import httpx


DEFAULT_AGENT_OLLAMA_BASE_URLS = ("http://127.0.0.1:11435",)
AGENT_OLLAMA_BASE_URLS_ENV = "VANTAGE_AGENT_OLLAMA_BASE_URLS"
CAPABILITY_CHECK_PROMPT = (
    "Reply with a compact JSON object describing the model health for this control-plane check. "
    'Use keys "mode", "json", and "notes". Return JSON only.'
)
RECENT_RUNS: deque[dict] = deque(maxlen=25)


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


def _run_id(*parts: str) -> str:
    stable = "::".join(parts)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def _active_model_runs() -> list[dict]:
    runs: list[dict] = []
    observed_at = datetime.now(UTC)
    for base_url in resolve_ollama_base_urls():
        try:
            response = httpx.get(f"{base_url}/api/ps", timeout=5.0)
            response.raise_for_status()
        except Exception:
            continue

        for model in response.json().get("models", []):
            model_name = model.get("name") or model.get("model")
            if not model_name:
                continue

            digest = model.get("digest") or ""
            run_id = _run_id("ollama_loaded_model", "bastet", model_name, digest, base_url)
            runs.append(
                {
                    "run_id": run_id,
                    "source_type": "remote_agent",
                    "detail_type": "ollama_loaded_model",
                    "source_id": f"ollama-ps:{base_url}:{model_name}",
                    "node_id": "bastet",
                    "model_name": model_name,
                    "action_type": "infer",
                    "status": "running",
                    "started_at": observed_at,
                    "ended_at": None,
                    "duration_ms": None,
                    "summary": f"Model {model_name} is currently loaded on bastet",
                    "metadata_json": {
                        "base_url": base_url,
                        "digest": model.get("digest"),
                        "size_vram": model.get("size_vram"),
                        "expires_at": model.get("expires_at"),
                    },
                }
            )
    return runs


def _record_run(run: dict) -> dict:
    RECENT_RUNS.appendleft(run)
    return run


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
    recent_capability_runs = list(RECENT_RUNS)
    active_model_runs = _active_model_runs()
    merged: dict[str, dict] = {run["run_id"]: run for run in recent_capability_runs}
    for run in active_model_runs:
        merged[run["run_id"]] = run
    return sorted(merged.values(), key=lambda run: run["started_at"], reverse=True)


def run_capability_check(model_name: str, *, prompt: str | None = None) -> dict:
    request_prompt = prompt or CAPABILITY_CHECK_PROMPT
    started_at = datetime.now(UTC)
    payload = {
        "model": model_name,
        "prompt": request_prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 96,
        },
    }
    errors: list[dict] = []

    for base_url in resolve_ollama_base_urls():
        try:
            response = httpx.post(f"{base_url}/api/generate", json=payload, timeout=45.0)
            response.raise_for_status()
            body = response.json()
            ended_at = datetime.now(UTC)
            result = _record_run(
                {
                    "run_id": str(uuid4()),
                    "source_type": "inference",
                    "detail_type": "capability_check",
                    "source_id": f"capability-check:bastet:{model_name}",
                    "node_id": "bastet",
                    "model_name": model_name,
                    "action_type": "infer",
                    "status": "success",
                    "started_at": started_at,
                    "ended_at": ended_at,
                    "duration_ms": int((ended_at - started_at).total_seconds() * 1000),
                    "summary": f"Capability check passed for {model_name} on bastet",
                    "metadata_json": {
                        "base_url": base_url,
                        "prompt": request_prompt,
                        "response_preview": body.get("response", "")[:240],
                    },
                }
            )
            return result
        except Exception as exc:
            errors.append({"base_url": base_url, "error": str(exc)})

    ended_at = datetime.now(UTC)
    failure = _record_run(
        {
            "run_id": str(uuid4()),
            "source_type": "inference",
            "detail_type": "capability_check",
            "source_id": f"capability-check:bastet:{model_name}",
            "node_id": "bastet",
            "model_name": model_name,
            "action_type": "infer",
            "status": "failed",
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_ms": int((ended_at - started_at).total_seconds() * 1000),
            "summary": f"Capability check failed for {model_name} on bastet",
            "metadata_json": {
                "prompt": request_prompt,
                "errors": errors,
            },
        }
    )
    return failure
