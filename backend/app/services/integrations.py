from __future__ import annotations

import ipaddress
import os
import socket
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
WEBHOOK_ALLOW_PRIVATE_NETWORKS_ENV = "VANTAGE_WEBHOOK_ALLOW_PRIVATE_NETWORKS"
EMAIL_SMTP_HOST_ENV = "VANTAGE_EMAIL_SMTP_HOST"
EMAIL_SMTP_PORT_ENV = "VANTAGE_EMAIL_SMTP_PORT"
EMAIL_SMTP_USERNAME_ENV = "VANTAGE_EMAIL_SMTP_USERNAME"
EMAIL_SMTP_PASSWORD_ENV = "VANTAGE_EMAIL_SMTP_PASSWORD"
EMAIL_FROM_ENV = "VANTAGE_EMAIL_FROM"
EMAIL_TO_ENV = "VANTAGE_EMAIL_TO"
EMAIL_USE_TLS_ENV = "VANTAGE_EMAIL_USE_TLS"
INTEGRATION_LAST_DISPATCH_KEY = "integration_last_dispatch"
PRIVATE_WEBHOOK_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
)


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


def _target_matches_allowed_host(url: str, allowed_host: str) -> bool:
    target = urlparse(url)
    allowed = urlparse(f"//{allowed_host}")
    if not target.hostname or not allowed.hostname:
        return False
    if target.hostname.lower().rstrip(".") != allowed.hostname.lower().rstrip("."):
        return False
    try:
        allowed_port = allowed.port
    except ValueError:
        return False
    if allowed_port is None:
        return target.port is None
    target_port = target.port or (443 if target.scheme == "https" else 80)
    return target_port == allowed_port


def _require_public_webhook_addresses(hostname: str, port: int) -> None:
    try:
        address_info = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError("Webhook target could not be resolved") from exc
    if not address_info:
        raise ValueError("Webhook target could not be resolved")

    for info in address_info:
        address = info[4][0].split("%", 1)[0]
        try:
            parsed_address = ipaddress.ip_address(address)
        except ValueError as exc:
            raise ValueError("Webhook target resolved to an invalid address") from exc
        private_networks_allowed = os.getenv(WEBHOOK_ALLOW_PRIVATE_NETWORKS_ENV, "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        is_explicitly_allowed_private = private_networks_allowed and any(
            parsed_address in network for network in PRIVATE_WEBHOOK_NETWORKS
        )
        if not parsed_address.is_global and not is_explicitly_allowed_private:
            raise ValueError("Webhook target resolves to a non-public address")


def validate_webhook_target(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
        raise ValueError("Webhook target must be an http or https URL")
    if parsed.username or parsed.password:
        raise ValueError("Webhook target must not include user information")
    try:
        target_port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise ValueError("Webhook target port is invalid") from exc

    allowed_hosts = {host.strip().lower() for host in os.getenv(WEBHOOK_ALLOWED_HOSTS_ENV, "").split(",") if host.strip()}
    if not allowed_hosts:
        raise ValueError("VANTAGE_WEBHOOK_ALLOWED_HOSTS must explicitly allow the webhook target")
    if not any(_target_matches_allowed_host(url, allowed_host) for allowed_host in allowed_hosts):
        raise ValueError("Webhook target host is not in VANTAGE_WEBHOOK_ALLOWED_HOSTS")
    _require_public_webhook_addresses(parsed.hostname, target_port)


def redact_webhook_target(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "<redacted>"
    hostname = parsed.hostname
    authority = f"[{hostname}]" if ":" in hostname else hostname
    try:
        if parsed.port is not None:
            authority = f"{authority}:{parsed.port}"
    except ValueError:
        return "<redacted>"
    return f"{parsed.scheme}://{authority}/<redacted>"


def _sanitize_dispatch_result(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if result is None:
        return None
    sanitized = dict(result)
    target_url = sanitized.get("target_url")
    if isinstance(target_url, str):
        sanitized["target_url"] = redact_webhook_target(target_url)
    return sanitized


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
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        response = await client.post(target_url, json=payload)
        response.raise_for_status()
    return {
        "adapter": adapter,
        "target_url": redact_webhook_target(target_url),
        "event_count": len(events),
        "status_code": response.status_code,
    }


def record_integration_dispatch(session: Session, result: dict[str, Any]) -> dict[str, Any]:
    payload = {**(_sanitize_dispatch_result(result) or {}), "dispatched_at": datetime.now(UTC).isoformat()}
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
        "last_dispatch": _sanitize_dispatch_result(get_app_setting(session, INTEGRATION_LAST_DISPATCH_KEY, None)),
        "security_event_counters": list_security_event_counters(session),
    }
