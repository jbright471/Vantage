from datetime import UTC, datetime
from collections.abc import Sequence
import os

from sqlalchemy.orm import Session

from backend.app.models import AppSetting

LOCAL_OLLAMA_ENDPOINT_OVERRIDES_KEY = "local_ollama_endpoint_overrides"
DEFAULT_LOCAL_OLLAMA_BASE_URLS = ("http://127.0.0.1:11400",)
LOCAL_OLLAMA_BASE_URLS_ENV = "VANTAGE_LOCAL_OLLAMA_BASE_URLS"


def normalize_endpoint_url(value: str) -> str:
    return value.strip().rstrip("/")


def resolve_local_ollama_base_urls(configured_urls: Sequence[str] | None = None) -> list[str]:
    raw_urls = os.getenv(LOCAL_OLLAMA_BASE_URLS_ENV)
    if raw_urls:
        candidates = [part.strip() for part in raw_urls.split(",")]
    elif configured_urls:
        candidates = list(configured_urls)
    else:
        candidates = list(DEFAULT_LOCAL_OLLAMA_BASE_URLS)

    return [normalize_endpoint_url(candidate) for candidate in candidates if candidate.strip()]


def get_disabled_local_ollama_endpoints(session: Session) -> set[str]:
    setting = session.get(AppSetting, LOCAL_OLLAMA_ENDPOINT_OVERRIDES_KEY)
    if setting is None:
        return set()
    endpoints = setting.value_json.get("disabled", [])
    if not isinstance(endpoints, list):
        return set()
    return {normalize_endpoint_url(str(endpoint)) for endpoint in endpoints}


def filter_enabled_local_ollama_endpoints(session: Session, configured_urls: Sequence[str]) -> list[str]:
    disabled = get_disabled_local_ollama_endpoints(session)
    return [url for url in resolve_local_ollama_base_urls(configured_urls) if url not in disabled]


def set_local_ollama_endpoint_disabled(session: Session, endpoint_url: str, disabled: bool) -> dict:
    normalized_url = normalize_endpoint_url(endpoint_url)
    disabled_endpoints = get_disabled_local_ollama_endpoints(session)
    previous_disabled = normalized_url in disabled_endpoints

    if disabled:
        disabled_endpoints.add(normalized_url)
    else:
        disabled_endpoints.discard(normalized_url)

    setting = session.get(AppSetting, LOCAL_OLLAMA_ENDPOINT_OVERRIDES_KEY)
    value_json = {"disabled": sorted(disabled_endpoints)}
    if setting is None:
        session.add(
            AppSetting(
                key=LOCAL_OLLAMA_ENDPOINT_OVERRIDES_KEY,
                value_json=value_json,
                updated_at=datetime.now(UTC),
            )
        )
    else:
        setting.value_json = value_json
        setting.updated_at = datetime.now(UTC)

    return {
        "endpoint_url": normalized_url,
        "previous_disabled": previous_disabled,
        "requested_disabled": disabled,
        "changed": previous_disabled != disabled,
        "disabled_endpoints": value_json["disabled"],
    }
