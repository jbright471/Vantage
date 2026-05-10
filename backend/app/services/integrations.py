from __future__ import annotations

import os
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Run, WarningRecord
from backend.app.services.app_settings import get_app_setting, set_app_setting
from backend.app.services.runs import serialize_run
from backend.app.services.security_events import list_security_event_counters


GENERIC_WEBHOOK_URL_ENV = "VANTAGE_WEBHOOK_URL"
SLACK_WEBHOOK_URL_ENV = "VANTAGE_SLACK_WEBHOOK_URL"
DISCORD_WEBHOOK_URL_ENV = "VANTAGE_DISCORD_WEBHOOK_URL"
WEBHOOK_ALLOWED_HOSTS_ENV = "VANTAGE_WEBHOOK_ALLOWED_HOSTS"
EMAIL_SMTP_HOST_ENV = "VANTAGE_EMAIL_SMTP_HOST"
EMAIL_SMTP_PORT_ENV = "VANTAGE_EMAIL_SMTP_PORT"
EMAIL_SMTP_USERNAME_ENV = "VANTAGE_EMAIL_SMTP_USERNAME"
EMAIL_SMTP_PASSWORD_ENV = "VANTAGE_EMAIL_SMTP_PASSWORD"
EMAIL_FROM_ENV = "VANTAGE_EMAIL_FROM"
EMAIL_TO_ENV = "VANTAGE_EMAIL_TO"
EMAIL_USE_TLS_ENV = "VANTAGE_EMAIL_USE_TLS"
INTEGRATION_LAST_DISPATCH_KEY = "integration_last_dispatch"


def _event_id(prefix: str, value: str) -> str:
    return f"{prefix}:{value}"


def _event_timestamp(value: datetime) -> str:
    timestamp = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return timestamp.isoformat()


def build_integration_events(
    session: Session,
    *,
    include_warnings: bool = True,
    include_failed_runs: bool = True,
    include_eval_regressions: bool = True,
    limit: int = 50,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    if include_warnings:
        warnings = session.scalars(
            select(WarningRecord)
            .where(WarningRecord.status.in_(("active", "acknowledged")))
            .order_by(WarningRecord.last_seen_at.desc())
            .limit(limit)
        ).all()
        for warning in warnings:
            events.append(
                {
                    "event_id": _event_id("warning", warning.warning_id),
                    "event_type": "warning",
                    "severity": warning.severity,
                    "occurred_at": _event_timestamp(warning.last_seen_at),
                    "summary": warning.summary,
                    "node_id": warning.node_id,
                    "payload": {
                        "warning_id": warning.warning_id,
                        "warning_type": warning.warning_type,
                        "status": warning.status,
                        "metadata_json": warning.metadata_json,
                    },
                }
            )

    if include_failed_runs:
        failed_runs = session.scalars(
            select(Run).where(Run.status == "failed").order_by(Run.started_at.desc()).limit(limit)
        ).all()
        for run in failed_runs:
            events.append(
                {
                    "event_id": _event_id("run", run.run_id),
                    "event_type": "failed_run",
                    "severity": "critical" if run.detail_type == "agent_action" else "warning",
                    "occurred_at": _event_timestamp(run.started_at),
                    "summary": run.summary,
                    "node_id": run.node_id,
                    "payload": serialize_run(run),
                }
            )

    if include_eval_regressions:
        eval_runs = session.scalars(
            select(Run)
            .where(Run.detail_type == "eval_attempt", Run.status == "failed")
            .order_by(Run.started_at.desc())
            .limit(limit)
        ).all()
        for run in eval_runs:
            score = (run.metadata_json or {}).get("score")
            if not isinstance(score, dict) or score.get("passed") is not False:
                continue
            events.append(
                {
                    "event_id": _event_id("eval", run.run_id),
                    "event_type": "eval_regression",
                    "severity": "warning",
                    "occurred_at": _event_timestamp(run.started_at),
                    "summary": f"Eval regression candidate: {run.summary}",
                    "node_id": run.node_id,
                    "payload": {
                        "run": serialize_run(run),
                        "score": score,
                    },
                }
            )

    return sorted(events, key=lambda event: event["occurred_at"], reverse=True)[:limit]


def resolve_webhook_url(adapter: str, explicit_url: str | None = None) -> str | None:
    if explicit_url:
        return explicit_url
    if adapter == "slack":
        return os.getenv(SLACK_WEBHOOK_URL_ENV)
    if adapter == "discord":
        return os.getenv(DISCORD_WEBHOOK_URL_ENV)
    return os.getenv(GENERIC_WEBHOOK_URL_ENV)


def email_configured() -> bool:
    return bool(os.getenv(EMAIL_SMTP_HOST_ENV) and os.getenv(EMAIL_FROM_ENV) and os.getenv(EMAIL_TO_ENV))


def validate_webhook_target(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Webhook target must be an http or https URL")
    allowed_hosts = {host.strip().lower() for host in os.getenv(WEBHOOK_ALLOWED_HOSTS_ENV, "").split(",") if host.strip()}
    if allowed_hosts and (parsed.hostname or "").lower() not in allowed_hosts:
        raise ValueError("Webhook target host is not in VANTAGE_WEBHOOK_ALLOWED_HOSTS")


def build_webhook_payload(adapter: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    if adapter == "slack":
        text = "\n".join(f"- [{event['severity']}] {event['summary']}" for event in events[:10]) or "No events."
        return {"text": f"Vantage integration report\n{text}"}
    if adapter == "discord":
        description = "\n".join(f"**{event['severity']}**: {event['summary']}" for event in events[:10]) or "No events."
        return {"embeds": [{"title": "Vantage integration report", "description": description}]}
    return {
        "source": "vantage",
        "format": "vantage.integration.events.v1",
        "dispatched_at": datetime.now(UTC).isoformat(),
        "events": events,
    }


def build_email_message(events: list[dict[str, Any]]) -> EmailMessage:
    sender = os.getenv(EMAIL_FROM_ENV, "")
    recipients = [item.strip() for item in os.getenv(EMAIL_TO_ENV, "").split(",") if item.strip()]
    text = "\n".join(f"- [{event['severity']}] {event['summary']}" for event in events[:25]) or "No events."
    message = EmailMessage()
    message["Subject"] = "Vantage integration report"
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content(f"Vantage integration report\n\n{text}\n")
    return message


def dispatch_email(events: list[dict[str, Any]]) -> dict[str, Any]:
    if not email_configured():
        raise ValueError("Email adapter requires SMTP host, sender, and recipient configuration")
    host = os.getenv(EMAIL_SMTP_HOST_ENV, "")
    port = int(os.getenv(EMAIL_SMTP_PORT_ENV, "587"))
    username = os.getenv(EMAIL_SMTP_USERNAME_ENV)
    password = os.getenv(EMAIL_SMTP_PASSWORD_ENV)
    use_tls = os.getenv(EMAIL_USE_TLS_ENV, "1").lower() not in {"0", "false", "no"}
    message = build_email_message(events)
    with smtplib.SMTP(host, port, timeout=10) as smtp:
        if use_tls:
            smtp.starttls()
        if username and password:
            smtp.login(username, password)
        smtp.send_message(message)
    return {"adapter": "email", "event_count": len(events), "status_code": 202}


async def dispatch_webhook(adapter: str, target_url: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    validate_webhook_target(target_url)
    payload = build_webhook_payload(adapter, events)
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(target_url, json=payload)
        response.raise_for_status()
    return {
        "adapter": adapter,
        "target_url": target_url,
        "event_count": len(events),
        "status_code": response.status_code,
    }


def record_integration_dispatch(session: Session, result: dict[str, Any]) -> dict[str, Any]:
    payload = {**result, "dispatched_at": datetime.now(UTC).isoformat()}
    set_app_setting(session, INTEGRATION_LAST_DISPATCH_KEY, payload)
    return payload


def build_integration_health(session: Session) -> dict[str, Any]:
    configured_targets = {
        "generic": bool(os.getenv(GENERIC_WEBHOOK_URL_ENV)),
        "slack": bool(os.getenv(SLACK_WEBHOOK_URL_ENV)),
        "discord": bool(os.getenv(DISCORD_WEBHOOK_URL_ENV)),
        "email": email_configured(),
    }
    return {
        "format": "vantage.integrations.health.v1",
        "external_api_token_configured": bool(os.getenv("VANTAGE_EXTERNAL_API_TOKEN")),
        "webhook_allowed_hosts_configured": bool(os.getenv(WEBHOOK_ALLOWED_HOSTS_ENV)),
        "configured_targets": configured_targets,
        "last_dispatch": get_app_setting(session, INTEGRATION_LAST_DISPATCH_KEY, None),
        "security_event_counters": list_security_event_counters(session),
    }
