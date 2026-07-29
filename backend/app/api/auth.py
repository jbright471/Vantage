import os
import secrets

from fastapi import Header, HTTPException


EXTERNAL_API_TOKEN_ENV = "VANTAGE_EXTERNAL_API_TOKEN"
MINIMUM_TOKEN_LENGTH = 32


def require_external_api_token(
    authorization: str | None = Header(default=None),
    x_vantage_api_key: str | None = Header(default=None),
) -> None:
    expected_token = os.getenv(EXTERNAL_API_TOKEN_ENV)
    if not expected_token or len(expected_token) < MINIMUM_TOKEN_LENGTH:
        raise HTTPException(status_code=503, detail="External API authentication is not configured")

    provided_token = x_vantage_api_key
    if not provided_token and authorization and authorization.lower().startswith("bearer "):
        provided_token = authorization.split(" ", 1)[1]

    if not provided_token or not secrets.compare_digest(provided_token, expected_token):
        raise HTTPException(status_code=401, detail="External API token required")
