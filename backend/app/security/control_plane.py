from __future__ import annotations

import os
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from backend.app.security.resource_limits import acquire_costly_request, is_costly_request


CONTROL_PLANE_TOKEN_ENV = "VANTAGE_CONTROL_PLANE_TOKEN"
SESSION_SIGNING_KEY_ENV = "VANTAGE_SESSION_SIGNING_KEY"
SESSION_MAX_AGE_ENV = "VANTAGE_SESSION_MAX_AGE_SECONDS"
SESSION_COOKIE_SECURE_ENV = "VANTAGE_SESSION_COOKIE_SECURE"
EXTERNAL_API_TOKEN_ENV = "VANTAGE_EXTERNAL_API_TOKEN"

SESSION_COOKIE_NAME = "vantage_session"
CSRF_COOKIE_NAME = "vantage_csrf"
CSRF_HEADER_NAME = "x-vantage-csrf"
SESSION_SALT = "vantage-control-plane-session-v1"
DEFAULT_SESSION_MAX_AGE_SECONDS = 8 * 60 * 60
MINIMUM_SECRET_LENGTH = 32
LOGIN_WINDOW_SECONDS = 5 * 60
LOGIN_MAX_FAILURES = 5
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
PUBLIC_API_PATHS = {
    "/api/health",
    "/api/health/live",
    "/api/health/ready",
    "/api/auth/login",
    "/api/auth/status",
}

_login_failures: dict[str, deque[float]] = {}
_login_lock = threading.Lock()


@dataclass(frozen=True)
class AuthenticationResult:
    mode: str
    csrf_token: str | None = None


def _configured_secret(name: str) -> str | None:
    value = os.getenv(name, "")
    return value if len(value) >= MINIMUM_SECRET_LENGTH else None


def control_plane_auth_configured() -> bool:
    return bool(_configured_secret(CONTROL_PLANE_TOKEN_ENV) and _configured_secret(SESSION_SIGNING_KEY_ENV))


def session_max_age_seconds() -> int:
    try:
        value = int(os.getenv(SESSION_MAX_AGE_ENV, str(DEFAULT_SESSION_MAX_AGE_SECONDS)))
    except ValueError:
        return DEFAULT_SESSION_MAX_AGE_SECONDS
    return max(300, min(value, 7 * 24 * 60 * 60))


def secure_session_cookie_enabled() -> bool:
    return os.getenv(SESSION_COOKIE_SECURE_ENV, "0").strip().lower() in {"1", "true", "yes", "on"}


def _serializer() -> URLSafeTimedSerializer | None:
    signing_key = _configured_secret(SESSION_SIGNING_KEY_ENV)
    if not signing_key:
        return None
    return URLSafeTimedSerializer(signing_key, salt=SESSION_SALT)


def issue_operator_session() -> tuple[str, str]:
    serializer = _serializer()
    if serializer is None:
        raise RuntimeError("Control-plane authentication is not configured")
    csrf_token = secrets.token_urlsafe(32)
    session_cookie = serializer.dumps({"subject": "operator", "csrf": csrf_token})
    return session_cookie, csrf_token


def _bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        return None
    return authorization.split(" ", 1)[1]


def _matches_secret(provided: str | None, expected: str | None) -> bool:
    return bool(provided and expected and secrets.compare_digest(provided, expected))


def authenticate_control_plane_request(request: Request) -> AuthenticationResult | None:
    expected_token = _configured_secret(CONTROL_PLANE_TOKEN_ENV)
    if _matches_secret(_bearer_token(request), expected_token):
        return AuthenticationResult(mode="bearer")

    serializer = _serializer()
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if serializer is None or not session_cookie:
        return None
    try:
        payload = serializer.loads(session_cookie, max_age=session_max_age_seconds())
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(payload, dict) or payload.get("subject") != "operator":
        return None
    csrf_token = payload.get("csrf")
    if not isinstance(csrf_token, str) or len(csrf_token) < MINIMUM_SECRET_LENGTH:
        return None
    return AuthenticationResult(mode="session", csrf_token=csrf_token)


def _valid_external_integration_auth(request: Request) -> bool:
    if not request.url.path.startswith("/api/integrations/"):
        return False
    expected = _configured_secret(EXTERNAL_API_TOKEN_ENV)
    provided = request.headers.get("x-vantage-api-key") or _bearer_token(request)
    return _matches_secret(provided, expected)


def _valid_csrf(request: Request, authentication: AuthenticationResult) -> bool:
    if authentication.mode != "session" or request.method.upper() in SAFE_METHODS:
        return True
    header_token = request.headers.get(CSRF_HEADER_NAME)
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    return bool(
        authentication.csrf_token
        and header_token
        and cookie_token
        and secrets.compare_digest(header_token, authentication.csrf_token)
        and secrets.compare_digest(cookie_token, authentication.csrf_token)
    )


def _apply_security_headers(response: Response, request: Request) -> None:
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cross-Origin-Embedder-Policy", "require-corp")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
    if request.url.scheme == "https" or forwarded_proto == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")


async def control_plane_security_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    path = request.url.path
    response: Response
    if not path.startswith("/api/") or path in PUBLIC_API_PATHS:
        response = await call_next(request)
    elif _valid_external_integration_auth(request):
        response = await call_next(request)
    elif not control_plane_auth_configured():
        response = JSONResponse(status_code=503, content={"detail": "Control-plane authentication is not configured"})
    else:
        authentication = authenticate_control_plane_request(request)
        if authentication is None:
            response = JSONResponse(status_code=401, content={"detail": "Control-plane authentication required"})
        elif not _valid_csrf(request, authentication):
            response = JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})
        else:
            lease = None
            if is_costly_request(request.method, path):
                source = f"{login_source(request)}:operator"
                limit_result = acquire_costly_request(source)
                lease = limit_result.lease
                if lease is None:
                    detail = "LLM request rate limit exceeded" if limit_result.reason == "rate" else "LLM concurrency limit reached"
                    response = JSONResponse(
                        status_code=429,
                        content={"detail": detail},
                        headers={"Retry-After": "60" if limit_result.reason == "rate" else "5"},
                    )
                else:
                    try:
                        response = await call_next(request)
                    finally:
                        lease.release()
            else:
                response = await call_next(request)
    _apply_security_headers(response, request)
    return response


def login_source(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def login_rate_limited(source: str, now: float | None = None) -> bool:
    current_time = time.monotonic() if now is None else now
    with _login_lock:
        failures = _login_failures.setdefault(source, deque())
        while failures and current_time - failures[0] > LOGIN_WINDOW_SECONDS:
            failures.popleft()
        return len(failures) >= LOGIN_MAX_FAILURES


def record_login_failure(source: str, now: float | None = None) -> None:
    current_time = time.monotonic() if now is None else now
    with _login_lock:
        _login_failures.setdefault(source, deque()).append(current_time)


def clear_login_failures(source: str) -> None:
    with _login_lock:
        _login_failures.pop(source, None)
