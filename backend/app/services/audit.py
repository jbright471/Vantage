from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import UTC, datetime
from typing import Any


AUDIT_SIGNING_KEY_ENV = "VANTAGE_AUDIT_SIGNING_KEY"
AUDIT_KEY_ID_ENV = "VANTAGE_AUDIT_KEY_ID"


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def resolve_audit_signing_key() -> str | None:
    signing_key = os.getenv(AUDIT_SIGNING_KEY_ENV)
    return signing_key if signing_key else None


def build_signed_audit_bundle(
    runs: list[dict[str, Any]],
    filters: dict[str, str | None],
    *,
    signing_key: str,
    key_id: str | None = None,
) -> dict[str, Any]:
    exported_at = datetime.now(UTC).isoformat()
    payload = {"runs": runs}
    unsigned_bundle = {
        "format": "vantage.audit.bundle.v1",
        "exported_at": exported_at,
        "filters": filters,
        "count": len(runs),
        "payload_sha256": payload_sha256(payload),
        "payload": payload,
    }
    signature_value = hmac.new(
        signing_key.encode("utf-8"),
        canonical_json(unsigned_bundle).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        **unsigned_bundle,
        "signature": {
            "algorithm": "HMAC-SHA256",
            "key_id": key_id or os.getenv(AUDIT_KEY_ID_ENV, "local-audit-key"),
            "signed_fields": list(unsigned_bundle.keys()),
            "value": signature_value,
        },
    }
