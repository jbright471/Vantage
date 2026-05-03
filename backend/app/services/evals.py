from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import BootstrapConfig
from backend.app.models import EvalCase, EvalSuite, Node, Run


def queue_eval_case_runs(
    session: Session,
    *,
    suite: EvalSuite,
    cases: list[EvalCase],
    model_name: str,
    node_id: str,
    trigger: str = "manual",
    schedule_id: str | None = None,
    started_at: datetime | None = None,
) -> dict[str, Any]:
    attempt_id = str(uuid4())
    queued_at = started_at or datetime.now(UTC)
    runs: list[Run] = []

    for eval_case in cases:
        metadata: dict[str, Any] = {
            "attempt_id": attempt_id,
            "suite_id": suite.suite_id,
            "suite_name": suite.name,
            "case_id": eval_case.case_id,
            "case_name": eval_case.name,
            "prompt": eval_case.prompt,
            "expected_json": eval_case.expected_json,
            "sort_order": eval_case.sort_order,
            "trigger": trigger,
        }
        if schedule_id is not None:
            metadata["schedule_id"] = schedule_id

        run = Run(
            run_id=str(uuid4()),
            source_type="eval",
            detail_type="eval_attempt",
            source_id=f"eval-suite:{suite.suite_id}:case:{eval_case.case_id}",
            node_id=node_id,
            model_name=model_name,
            action_type="eval",
            status="queued",
            started_at=queued_at,
            summary=f"Queued eval case '{eval_case.name}' for {model_name} on {node_id}",
            metadata_json=metadata,
        )
        session.add(run)
        runs.append(run)

    return {
        "attempt_id": attempt_id,
        "suite_id": suite.suite_id,
        "suite_name": suite.name,
        "model_name": model_name,
        "node_id": node_id,
        "run_count": len(runs),
        "runs": runs,
    }


def build_score_history(session: Session) -> dict[str, Any]:
    runs = session.scalars(
        select(Run)
        .where(Run.detail_type == "eval_attempt")
        .where(Run.status.in_(["success", "failed"]))
        .order_by(Run.started_at.desc())
    ).all()
    scored_runs: list[dict[str, Any]] = []
    for run in runs:
        row = _score_history_row(run)
        if row is not None:
            scored_runs.append(row)

    placements = _aggregate_score_rows(scored_runs, ["model_name", "node_id"])
    suites = _aggregate_score_rows(scored_runs, ["suite_id", "suite_name"])
    cases = _aggregate_score_rows(scored_runs, ["suite_id", "suite_name", "case_id", "case_name"])

    return {
        "total_runs": len(scored_runs),
        "placements": placements,
        "suites": suites,
        "cases": cases,
        "recent_runs": scored_runs[:20],
    }


def _score_history_row(run: Run) -> dict[str, Any] | None:
    metadata = run.metadata_json or {}
    score = metadata.get("score")
    if not isinstance(score, dict) or not isinstance(score.get("passed"), bool):
        return None

    return {
        "run_id": run.run_id,
        "suite_id": str(metadata.get("suite_id") or "unknown"),
        "suite_name": str(metadata.get("suite_name") or "Unknown suite"),
        "case_id": str(metadata.get("case_id") or "unknown"),
        "case_name": str(metadata.get("case_name") or "Unknown case"),
        "model_name": run.model_name or "unknown",
        "node_id": run.node_id,
        "status": run.status,
        "passed": score["passed"],
        "score": score.get("score"),
        "reason": score.get("reason"),
        "missing_or_mismatched": score.get("missing_or_mismatched", []),
        "response_preview": str(metadata.get("response_preview") or ""),
        "response_json": metadata.get("response_json"),
        "started_at": run.started_at.isoformat(),
        "duration_ms": run.duration_ms,
    }


def _aggregate_score_rows(rows: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in rows:
        group_key = tuple(str(row[key]) for key in keys)
        if group_key not in grouped:
            grouped[group_key] = {key: row[key] for key in keys}
            grouped[group_key].update({"run_count": 0, "passed_count": 0, "failed_count": 0, "latest_started_at": None})

        group = grouped[group_key]
        group["run_count"] += 1
        if row["passed"]:
            group["passed_count"] += 1
        else:
            group["failed_count"] += 1
        if group["latest_started_at"] is None or row["started_at"] > group["latest_started_at"]:
            group["latest_started_at"] = row["started_at"]

    aggregates = []
    for group in grouped.values():
        run_count = group["run_count"]
        group["pass_rate"] = round(group["passed_count"] / run_count, 4) if run_count else 0.0
        aggregates.append(group)

    return sorted(
        aggregates,
        key=lambda row: (
            -row["pass_rate"],
            -row["run_count"],
            str(row.get("model_name") or row.get("suite_name")),
            str(row.get("case_name") or ""),
        ),
    )


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
