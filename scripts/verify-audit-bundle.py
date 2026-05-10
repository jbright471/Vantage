from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path
from typing import Any


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a Vantage signed audit bundle.")
    parser.add_argument("bundle", help="Path to export.bundle.json")
    parser.add_argument("--key", default=os.getenv("VANTAGE_AUDIT_SIGNING_KEY"), help="Audit signing key")
    args = parser.parse_args()

    if not args.key:
        print("Missing signing key. Pass --key or set VANTAGE_AUDIT_SIGNING_KEY.", file=sys.stderr)
        return 2

    bundle = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    signature = bundle.get("signature") or {}
    provided_signature = signature.get("value")
    if not provided_signature:
        print("Bundle is missing signature.value.", file=sys.stderr)
        return 1

    unsigned_bundle = {key: value for key, value in bundle.items() if key != "signature"}
    payload_digest = hashlib.sha256(canonical_json(unsigned_bundle.get("payload")).encode("utf-8")).hexdigest()
    if payload_digest != unsigned_bundle.get("payload_sha256"):
        print("Payload digest mismatch.", file=sys.stderr)
        return 1

    expected_signature = hmac.new(
        args.key.encode("utf-8"),
        canonical_json(unsigned_bundle).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(provided_signature, expected_signature):
        print("Signature mismatch.", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "verified": True,
                "format": bundle.get("format"),
                "key_id": signature.get("key_id"),
                "count": bundle.get("count"),
                "payload_sha256": payload_digest,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
