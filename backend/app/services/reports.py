from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Node, Run, WarningRecord


def build_operator_markdown_report(session: Session, *, title: str = "Vantage Operator Report") -> str:
    generated_at = datetime.now(UTC).isoformat()
    nodes = session.scalars(select(Node).order_by(Node.display_name)).all()
    warnings = session.scalars(
        select(WarningRecord)
        .where(WarningRecord.status.in_(("active", "acknowledged")))
        .order_by(WarningRecord.last_seen_at.desc())
        .limit(20)
    ).all()
    failed_runs = session.scalars(
        select(Run).where(Run.status == "failed").order_by(Run.started_at.desc()).limit(20)
    ).all()
    recent_eval_runs = session.scalars(
        select(Run)
        .where(Run.detail_type == "eval_attempt")
        .order_by(Run.started_at.desc())
        .limit(20)
    ).all()

    lines = [
        f"# {title}",
        "",
        f"- Generated at: `{generated_at}`",
        "- Source: `Vantage`",
        "",
        "## Fleet",
        "",
    ]

    if nodes:
        for node in nodes:
            last_seen = node.last_seen_at.isoformat() if node.last_seen_at else "never"
            lines.append(f"- `{node.node_id}` ({node.role}) enabled=`{node.enabled}` last_seen=`{last_seen}`")
    else:
        lines.append("- No nodes are registered.")

    lines.extend(["", "## Active Warnings", ""])
    if warnings:
        for warning in warnings:
            lines.append(f"- `{warning.severity}` `{warning.warning_type}` on `{warning.node_id or 'control-plane'}`: {warning.summary}")
    else:
        lines.append("- No active or acknowledged warnings.")

    lines.extend(["", "## Failed Runs", ""])
    if failed_runs:
        for run in failed_runs:
            lines.append(f"- `{run.run_id}` `{run.detail_type}` on `{run.node_id}`: {run.summary}")
    else:
        lines.append("- No failed runs in the recent window.")

    lines.extend(["", "## Recent Eval Runs", ""])
    if recent_eval_runs:
        for run in recent_eval_runs:
            score = (run.metadata_json or {}).get("score")
            passed = score.get("passed") if isinstance(score, dict) else "unknown"
            lines.append(f"- `{run.run_id}` passed=`{passed}` model=`{run.model_name}` node=`{run.node_id}`")
    else:
        lines.append("- No eval runs found.")

    lines.extend(
        [
            "",
            "## Operator Notes",
            "",
            "- Add incident observations here.",
            "- Link related run IDs, warnings, and external tickets.",
        ]
    )
    return "\n".join(lines) + "\n"
