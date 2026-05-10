from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.services.app_settings import get_app_setting, set_app_setting


EVAL_INTELLIGENCE_PRESETS_KEY = "eval_intelligence_presets"


def list_eval_intelligence_presets(session: Session) -> list[dict]:
    value = get_app_setting(session, EVAL_INTELLIGENCE_PRESETS_KEY, {"presets": []})
    presets = value.get("presets", []) if isinstance(value, dict) else []
    return [preset for preset in presets if isinstance(preset, dict)]


def upsert_eval_intelligence_preset(session: Session, payload: dict) -> dict:
    now = datetime.now(UTC).isoformat()
    preset_id = str(payload.get("id") or uuid4())
    preset = {
        "id": preset_id,
        "name": str(payload["name"]),
        "controls": dict(payload["controls"]),
        "created_at": str(payload.get("created_at") or now),
        "updated_at": now,
        "storage": "managed",
    }
    presets = [item for item in list_eval_intelligence_presets(session) if item.get("id") != preset_id and item.get("name") != preset["name"]]
    presets.append(preset)
    presets.sort(key=lambda item: str(item.get("name", "")))
    set_app_setting(session, EVAL_INTELLIGENCE_PRESETS_KEY, {"presets": presets})
    return preset


def delete_eval_intelligence_preset(session: Session, preset_id: str) -> bool:
    presets = list_eval_intelligence_presets(session)
    next_presets = [preset for preset in presets if preset.get("id") != preset_id]
    if len(next_presets) == len(presets):
        return False
    set_app_setting(session, EVAL_INTELLIGENCE_PRESETS_KEY, {"presets": next_presets})
    return True
