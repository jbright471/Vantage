from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend.app.db import SessionLocal
from backend.app.security.control_plane import (
    CONTROL_PLANE_TOKEN_ENV,
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    authenticate_control_plane_request,
    clear_login_failures,
    control_plane_auth_configured,
    issue_operator_session,
    login_rate_limited,
    login_source,
    record_login_failure,
    secure_session_cookie_enabled,
    session_max_age_seconds,
)
from backend.app.services.security_events import increment_security_event_counter


router = APIRouter()


class OperatorLoginRequest(BaseModel):
    token: str = Field(min_length=1, max_length=4096)


def _record_auth_event(event_type: str) -> None:
    try:
        with SessionLocal() as session:
            increment_security_event_counter(session, event_type=event_type)
    except Exception:
        return


@router.get("/auth/status")
def operator_auth_status(request: Request) -> dict[str, bool]:
    configured = control_plane_auth_configured()
    return {
        "configured": configured,
        "authenticated": configured and authenticate_control_plane_request(request) is not None,
    }


@router.post("/auth/login")
def operator_login(payload: OperatorLoginRequest, request: Request, response: Response) -> dict[str, bool]:
    if not control_plane_auth_configured():
        raise HTTPException(status_code=503, detail="Control-plane authentication is not configured")

    source = login_source(request)
    if login_rate_limited(source):
        _record_auth_event("control_plane_login_rate_limited")
        raise HTTPException(status_code=429, detail="Too many authentication attempts", headers={"Retry-After": "300"})

    expected_token = os.getenv(CONTROL_PLANE_TOKEN_ENV, "")
    if not secrets.compare_digest(payload.token, expected_token):
        record_login_failure(source)
        _record_auth_event("control_plane_auth_failed")
        raise HTTPException(status_code=401, detail="Control-plane authentication failed")

    clear_login_failures(source)
    session_cookie, csrf_token = issue_operator_session()
    max_age = session_max_age_seconds()
    secure = secure_session_cookie_enabled()
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_cookie,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=secure,
        samesite="strict",
        path="/",
    )
    _record_auth_event("control_plane_login_succeeded")
    return {"authenticated": True}


@router.post("/auth/logout")
def operator_logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")
    _record_auth_event("control_plane_logout")
    return {"authenticated": False}
