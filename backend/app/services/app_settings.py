from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models import AppSetting


def get_app_setting(session: Session, key: str, default: Any = None) -> Any:
    setting = session.get(AppSetting, key)
    if setting is None:
        return default
    return setting.value_json


def set_app_setting(session: Session, key: str, value: Any) -> AppSetting:
    setting = session.get(AppSetting, key)
    if setting is None:
        setting = AppSetting(key=key, value_json=value, updated_at=datetime.now(UTC))
        session.add(setting)
    else:
        setting.value_json = value
        setting.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(setting)
    return setting
