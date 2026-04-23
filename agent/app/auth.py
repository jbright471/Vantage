import os
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


AGENT_TOKEN_ENV = "VANTAGE_AGENT_SHARED_TOKEN"
bearer_scheme = HTTPBearer(auto_error=False)


def require_agent_auth(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]) -> None:
    expected_token = os.getenv(AGENT_TOKEN_ENV)
    if not expected_token:
        return

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Agent authentication required")

    if not secrets.compare_digest(credentials.credentials, expected_token):
        raise HTTPException(status_code=401, detail="Agent authentication required")
