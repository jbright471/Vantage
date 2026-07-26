from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from typing import Any

import httpx


class AgentAuthenticationError(RuntimeError):
    pass


class RemoteAgentClient:
    def __init__(
        self,
        base_url: str,
        auth_token: str | None = None,
        *,
        auth_mode: str = "bearer",
        key_id: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.auth_mode = auth_mode
        self.key_id = key_id

    def _signature_message(self, method: str, path: str, timestamp: str, nonce: str, body: bytes) -> str:
        body_sha256 = hashlib.sha256(body).hexdigest()
        return "\n".join([method.upper(), path, timestamp, nonce, body_sha256])

    def _headers(self, method: str, path: str, body: bytes = b"") -> dict[str, str]:
        if not self.auth_token:
            return {}

        auth_mode = self.auth_mode.lower()
        if auth_mode == "bearer":
            return {"Authorization": f"Bearer {self.auth_token}"}

        if auth_mode not in {"hmac", "bearer_or_hmac"}:
            raise ValueError(f"Unsupported agent auth mode '{self.auth_mode}'")

        timestamp = str(int(time.time()))
        nonce = secrets.token_urlsafe(18)
        message = self._signature_message(method, path, timestamp, nonce, body)
        signature = hmac.new(self.auth_token.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
        headers = {
            "X-Vantage-Timestamp": timestamp,
            "X-Vantage-Nonce": nonce,
            "X-Vantage-Signature": signature,
        }
        if self.key_id:
            headers["X-Vantage-Key-Id"] = self.key_id
        return headers

    def _raise_for_status(self, response: httpx.Response, path: str) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403}:
                raise AgentAuthenticationError(
                    f"Remote agent rejected authentication for {self.base_url}{path}"
                ) from exc
            raise

    async def _get(self, path: str) -> dict:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{self.base_url}{path}", headers=self._headers("GET", path))
            self._raise_for_status(response, path)
            return response.json()

    def post_json(self, path: str, payload: dict[str, Any], *, timeout: float) -> dict:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers = self._headers("POST", path, body)
        headers["Content-Type"] = "application/json"
        with httpx.Client(timeout=timeout) as client:
            response = client.post(f"{self.base_url}{path}", content=body, headers=headers)
            self._raise_for_status(response, path)
            return response.json()

    async def fetch_health(self) -> dict:
        return await self._get("/health")

    async def fetch_gpu(self) -> dict:
        return await self._get("/gpu")

    async def fetch_models(self) -> dict:
        return await self._get("/models")

    async def fetch_runs(self) -> dict:
        return await self._get("/runs")
