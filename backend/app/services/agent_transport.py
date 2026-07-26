from __future__ import annotations

import os

from backend.app.collectors.remote import RemoteAgentClient
from backend.app.config import BootstrapConfig
from backend.app.models import Node


AGENT_AUTH_MODE_ENV = "VANTAGE_AGENT_AUTH_MODE"
AGENT_KEY_ID_ENV = "VANTAGE_AGENT_KEY_ID"


def build_remote_agent_client(node: Node, config: BootstrapConfig) -> RemoteAgentClient:
    auth_config = node.auth_config_json or {}
    token_env = str(auth_config.get("token_env") or config.agent_auth_token_env)
    auth_token = os.getenv(token_env) or None
    auth_mode = node.auth_mode or os.getenv(AGENT_AUTH_MODE_ENV) or "hmac"
    key_id = str(auth_config.get("key_id") or os.getenv(AGENT_KEY_ID_ENV) or "") or None
    return RemoteAgentClient(
        node.base_url,
        auth_token=auth_token,
        auth_mode=auth_mode,
        key_id=key_id,
    )
