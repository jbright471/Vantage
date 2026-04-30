from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from backend.app.config import BootstrapConfig
from backend.app.models import Node, Run


def score_expected_json(response_text: str, expected_json: dict[str, Any]) -> dict[str, Any]:
    if not expected_json:
        return {"passed": True, "score": None, "reason": "no_expected_json"}

    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        return {"passed": False, "score": 0.0, "reason": "response_not_json"}

    if not isinstance(parsed, dict):
        return {"passed": False, "score": 0.0, "reason": "response_json_not_object"}

    missing_or_mismatched = [key for key, value in expected_json.items() if parsed.get(key) != value]
    passed = len(missing_or_mismatched) == 0
    return {
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "reason": "expected_subset_matched" if passed else "expected_subset_mismatch",
        "missing_or_mismatched": missing_or_mismatched,
    }


def parse_response_json(response_text: str) -> dict[str, Any] | list[Any] | None:
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, (dict, list)) else None


def execute_eval_run(
    session: Session,
    run: Run,
    *,
    node: Node,
    config: BootstrapConfig,
    auth_headers: dict[str, str] | None = None,
) -> Run:
    metadata = dict(run.metadata_json or {})
    prompt = metadata.get("prompt")
    expected_json = metadata.get("expected_json", {})
    if not isinstance(prompt, str) or not prompt.strip():
        _mark_eval_run_failed(run, metadata, "Eval run is missing prompt metadata.")
        session.commit()
        return run
    if not isinstance(expected_json, dict):
        expected_json = {}

    started_at = datetime.now(UTC)
    run.status = "running"
    run.started_at = started_at
    session.commit()

    payload = {
        "model": run.model_name,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0},
    }

    try:
        if node.role == "remote":
            response = httpx.post(
                f"{node.base_url}/eval-attempt",
                json={"model_name": run.model_name, "prompt": prompt, "expected_json": expected_json},
                headers=auth_headers or {},
                timeout=90.0,
            )
            response.raise_for_status()
            body = response.json()
            response_text = str(body.get("metadata_json", {}).get("response_text", ""))
            agent_score = body.get("metadata_json", {}).get("score")
            score = agent_score if isinstance(agent_score, dict) else score_expected_json(response_text, expected_json)
            agent_run_id = body.get("run_id")
        else:
            response_text = _run_local_eval(payload, config)
            score = score_expected_json(response_text, expected_json)
            agent_run_id = None

        ended_at = datetime.now(UTC)
        metadata.update(
            {
                "response_text": response_text,
                "response_preview": response_text[:500],
                "response_json": parse_response_json(response_text),
                "score": score,
            }
        )
        if agent_run_id:
            metadata["agent_run_id"] = agent_run_id

        run.status = "success" if score.get("passed") is not False else "failed"
        run.ended_at = ended_at
        run.duration_ms = int((ended_at - started_at).total_seconds() * 1000)
        run.summary = _summarize_eval_run(run, score)
        run.metadata_json = metadata
        session.commit()
        return run
    except Exception as exc:
        _mark_eval_run_failed(run, metadata, str(exc), started_at=started_at)
        session.commit()
        return run


def _run_local_eval(payload: dict[str, Any], config: BootstrapConfig) -> str:
    errors: list[dict[str, str]] = []
    for base_url in config.local_ollama_base_urls:
        try:
            response = httpx.post(f"{base_url}/api/generate", json=payload, timeout=90.0)
            response.raise_for_status()
            return str(response.json().get("response", ""))
        except Exception as exc:
            errors.append({"base_url": base_url, "error": str(exc)})
    raise RuntimeError(f"Local Ollama eval failed on all configured endpoints: {errors}")


def _summarize_eval_run(run: Run, score: dict[str, Any]) -> str:
    case_name = run.metadata_json.get("case_name", "eval case") if isinstance(run.metadata_json, dict) else "eval case"
    if score.get("passed") is False:
        return f"Eval case '{case_name}' failed for {run.model_name} on {run.node_id}"
    return f"Eval case '{case_name}' passed for {run.model_name} on {run.node_id}"


def _mark_eval_run_failed(
    run: Run,
    metadata: dict[str, Any],
    error: str,
    *,
    started_at: datetime | None = None,
) -> Run:
    ended_at = datetime.now(UTC)
    metadata.update({"errors": [{"error": error}]})
    run.status = "failed"
    run.ended_at = ended_at
    if started_at is not None:
        run.duration_ms = int((ended_at - started_at).total_seconds() * 1000)
    run.summary = f"Eval attempt failed for {run.model_name} on {run.node_id}"
    run.metadata_json = metadata
    return run
