from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


AGENT_TOKEN_ENV = "VANTAGE_AGENT_SHARED_TOKEN"
AGENT_AUTH_MODE_ENV = "VANTAGE_AGENT_AUTH_MODE"
AGENT_KEY_ID_ENV = "VANTAGE_AGENT_KEY_ID"
AGENT_ALLOWED_ACTIONS_ENV = "VANTAGE_AGENT_ALLOWED_ACTIONS"
AGENT_ALLOWED_SKEW_ENV = "VANTAGE_AGENT_AUTH_ALLOWED_SKEW_SECONDS"
AGENT_REPLAY_CACHE_ENV = "VANTAGE_AGENT_REPLAY_CACHE_SECONDS"

HMAC_TIMESTAMP_HEADER = "x-vantage-timestamp"
HMAC_NONCE_HEADER = "x-vantage-nonce"
HMAC_SIGNATURE_HEADER = "x-vantage-signature"
HMAC_KEY_ID_HEADER = "x-vantage-key-id"

DEFAULT_ALLOWED_ACTIONS = "read,capability_check,eval_attempt"
DEFAULT_AUTH_SKEW_SECONDS = 300
DEFAULT_REPLAY_CACHE_SECONDS = 600

bearer_scheme = HTTPBearer(auto_error=False)
_seen_nonces: dict[str, float] = {}


def clear_replay_cache() -> None:
    _seen_nonces.clear()


def signature_message(method: str, path: str, timestamp: str, nonce: str, body: bytes) -> str:
    body_sha256 = hashlib.sha256(body).hexdigest()
    return "\n".join([method.upper(), path, timestamp, nonce, body_sha256])


def sign_request_message(signing_key: str, message: str) -> str:
    return hmac.new(signing_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def _auth_mode() -> str:
    return os.getenv(AGENT_AUTH_MODE_ENV, "bearer").strip().lower()


def _allowed_actions() -> set[str]:
    configured = os.getenv(AGENT_ALLOWED_ACTIONS_ENV, DEFAULT_ALLOWED_ACTIONS)
    return {item.strip().lower() for item in configured.split(",") if item.strip()}


def _action_for_request(request: Request) -> str:
    if request.method.upper() == "GET":
        return "read"
    if request.url.path.endswith("/capability-check"):
        return "capability_check"
    if request.url.path.endswith("/eval-attempt"):
        return "eval_attempt"
    return "unknown"


def _require_action_allowed(request: Request) -> None:
    action = _action_for_request(request)
    if action not in _allowed_actions():
        raise HTTPException(status_code=403, detail=f"Agent action '{action}' is not allowed")


def _prune_replay_cache(now: float, cache_seconds: int) -> None:
    expired = [nonce for nonce, seen_at in _seen_nonces.items() if now - seen_at > cache_seconds]
    for nonce in expired:
        _seen_nonces.pop(nonce, None)


def _accept_bearer(
    expected_token: str,
    credentials: HTTPAuthorizationCredentials | None,
) -> bool:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return False
    return secrets.compare_digest(credentials.credentials, expected_token)


async def _require_hmac(request: Request, expected_token: str) -> None:
    timestamp = request.headers.get(HMAC_TIMESTAMP_HEADER)
    nonce = request.headers.get(HMAC_NONCE_HEADER)
    signature = request.headers.get(HMAC_SIGNATURE_HEADER)
    if not timestamp or not nonce or not signature:
        raise HTTPException(status_code=401, detail="Agent request signature required")

    expected_key_id = os.getenv(AGENT_KEY_ID_ENV)
    request_key_id = request.headers.get(HMAC_KEY_ID_HEADER)
    if expected_key_id and not secrets.compare_digest(request_key_id or "", expected_key_id):
        raise HTTPException(status_code=401, detail="Agent request signature required")

    try:
        request_time = int(timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid agent request timestamp") from exc

    now = time.time()
    allowed_skew = int(os.getenv(AGENT_ALLOWED_SKEW_ENV, str(DEFAULT_AUTH_SKEW_SECONDS)))
    replay_cache_seconds = int(os.getenv(AGENT_REPLAY_CACHE_ENV, str(DEFAULT_REPLAY_CACHE_SECONDS)))
    if abs(now - request_time) > allowed_skew:
        raise HTTPException(status_code=401, detail="Agent request timestamp outside allowed skew")

    _prune_replay_cache(now, replay_cache_seconds)
    if nonce in _seen_nonces:
        raise HTTPException(status_code=401, detail="Agent request replay rejected")

    body = await request.body()
    message = signature_message(request.method, request.url.path, timestamp, nonce, body)
    expected_signature = sign_request_message(expected_token, message)
    if not secrets.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=401, detail="Agent request signature required")

    _seen_nonces[nonce] = now


async def require_agent_auth(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> None:
    _require_action_allowed(request)

    expected_token = os.getenv(AGENT_TOKEN_ENV)
    if not expected_token:
        return

    mode = _auth_mode()
    if mode == "bearer":
        if _accept_bearer(expected_token, credentials):
            return
        raise HTTPException(status_code=401, detail="Agent authentication required")

    if mode == "hmac":
        await _require_hmac(request, expected_token)
        return

    if mode == "bearer_or_hmac":
        if _accept_bearer(expected_token, credentials):
            return
        await _require_hmac(request, expected_token)
        return

    raise HTTPException(status_code=500, detail=f"Unsupported agent auth mode '{mode}'")
