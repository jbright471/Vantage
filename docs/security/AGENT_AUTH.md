# Agent Authentication

Vantage supports two node-agent authentication modes. New installations default to HMAC request signing, timestamp checks, and replay protection. Bearer mode remains available for compatibility with existing trusted-LAN installations.

## Modes

| Mode | Value | Use When |
| --- | --- | --- |
| HMAC | `VANTAGE_AGENT_AUTH_MODE=hmac` | Recommended default for explicitly registered LAN or VPN workers. |
| Bearer | `VANTAGE_AGENT_AUTH_MODE=bearer` | Compatibility mode for an existing trusted-LAN installation. |
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

HMAC authenticates request contents but does not encrypt HTTP traffic. Restrict TCP `9110` to the control-plane IP on a trusted LAN, or carry the connection over a trusted VPN/TLS tunnel when prompts, responses, or telemetry cross a less-trusted network. Never publish the agent port to the internet.

On systemd hosts, pass `VANTAGE_AGENT_CONTROL_PLANE_CIDRS=<control-plane-ip>/32` to the installer to create a deny-by-default service network policy that still permits loopback access to the local model runtime. Retain host-firewall or VPN restrictions as defense in depth.

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
