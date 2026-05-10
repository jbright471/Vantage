from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.app.services.app_settings import get_app_setting, set_app_setting


SECURITY_EVENT_COUNTERS_KEY = "security_event_counters"


def increment_security_event_counter(
    session: Session,
    *,
    event_type: str,
    node_id: str | None = None,
    amount: int = 1,
) -> dict:
    value = get_app_setting(session, SECURITY_EVENT_COUNTERS_KEY, {"events": {}})
    events = dict(value.get("events", {})) if isinstance(value, dict) else {}
    key = f"{event_type}:{node_id or 'control-plane'}"
    current = dict(events.get(key, {}))
    current["event_type"] = event_type
    current["node_id"] = node_id
    current["count"] = int(current.get("count", 0)) + amount
    current["last_seen_at"] = datetime.now(UTC).isoformat()
    events[key] = current
    next_value = {"events": events}
    set_app_setting(session, SECURITY_EVENT_COUNTERS_KEY, next_value)
    return current


def list_security_event_counters(session: Session) -> list[dict]:
    value = get_app_setting(session, SECURITY_EVENT_COUNTERS_KEY, {"events": {}})
    events = value.get("events", {}) if isinstance(value, dict) else {}
    return sorted(
        [event for event in events.values() if isinstance(event, dict)],
        key=lambda item: str(item.get("last_seen_at", "")),
        reverse=True,
    )
