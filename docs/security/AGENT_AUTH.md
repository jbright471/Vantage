# Agent Authentication

Vantage supports two node-agent authentication modes. Bearer mode remains the default because it is simple for a single trusted LAN operator. HMAC mode is available when operators want request signing, timestamp checks, and replay protection.

## Modes

| Mode | Value | Use When |
| --- | --- | --- |
| Bearer | `VANTAGE_AGENT_AUTH_MODE=bearer` | Single-operator LAN or VPN deployments where a shared secret is sufficient. |
| HMAC | `VANTAGE_AGENT_AUTH_MODE=hmac` | Deployments that need signed requests and replay protection. |
| Migration | `VANTAGE_AGENT_AUTH_MODE=bearer_or_hmac` | Short transition windows while rotating clients from bearer to HMAC. |

All modes use `VANTAGE_AGENT_SHARED_TOKEN` as the shared secret. HMAC mode signs each request with:

Remote agents should also set `VANTAGE_AGENT_NODE_ID=<your-node-id>` so `/health`, `/runs`, capability checks, and eval attempts report the same identity configured in the control plane node registry.

```text
METHOD
PATH
UNIX_TIMESTAMP
NONCE
BODY_SHA256
```

The client sends:

```http
X-Vantage-Timestamp: <unix-seconds>
X-Vantage-Nonce: <unique-random-value>
X-Vantage-Signature: <hmac-sha256-hex>
X-Vantage-Key-Id: <optional-key-id>
```

The agent rejects requests with missing signatures, invalid signatures, stale timestamps, reused nonces, or mismatched key IDs.

## Least-Privilege Action Allowlist

Use `VANTAGE_AGENT_ALLOWED_ACTIONS` to restrict agent capabilities:

```text
VANTAGE_AGENT_ALLOWED_ACTIONS=read,capability_check,eval_attempt
```

| Action | Endpoints |
| --- | --- |
| `read` | `GET /health`, `GET /gpu`, `GET /models`, `GET /runs` |
| `capability_check` | `POST /capability-check` |
| `eval_attempt` | `POST /eval-attempt` |

Host-level remediation actions should be added only through an explicit local node-agent contract and a narrower allowlist.

## Replay Protection

HMAC mode stores recently seen nonces in memory and rejects duplicate nonces during the replay-cache window. Tune the window with:

```text
VANTAGE_AGENT_AUTH_ALLOWED_SKEW_SECONDS=300
VANTAGE_AGENT_REPLAY_CACHE_SECONDS=600
```

Keep clocks synchronized across the control-plane and agent nodes. If clocks drift beyond the allowed skew, signed requests will fail closed.

## Token Rotation

Generate a new token:

```powershell
.\scripts\rotate-agent-token.ps1
```

Apply it to a local env file:

```powershell
.\scripts\rotate-agent-token.ps1 -EnvFile .env.production -Apply
```

Then update every remote agent env file with the same token, restart the backend, restart each agent, and verify the remote `/health` endpoints.
