# Optional Local Node Agent

Vantage should not run the Dockerized backend as a privileged host-control process.

The optional local node agent is the escape hatch for host-level operations that require bare-metal access, such as service restarts, low-level NVIDIA telemetry, or future allowlisted remediation actions.

## Why This Exists

Docker containers are the wrong place for host remediation by default. Restarting host services or collecting privileged hardware details from inside the backend container usually requires risky patterns:

- `--privileged`
- Docker socket mounting
- broad host filesystem mounts
- elevated container capabilities

Vantage avoids those patterns. The backend remains an observer and coordinator. A local node agent, when installed, performs narrow host-level actions on the same machine under systemd with an explicit allowlist.

## Relationship To The Remote Agent

The local node agent should follow the same contract shape as the remote agent:

- FastAPI service on a local-only or trusted-LAN port
- bearer-token authentication
- strict Pydantic request and response models
- durable `Run` records for actions requested by the control plane
- no broad shell execution endpoint

For Phase 4 packaging, operators can install the existing generic Python agent on the control-plane host if they want bare-metal telemetry without giving the backend container extra privileges.

## Allowed Future Action Types

The local node agent may eventually support narrowly scoped actions such as:

| Action | Boundary |
| --- | --- |
| `restart_ollama` | Restart only the named Ollama service. |
| `reload_vantage_agent` | Restart only the Vantage agent service. |
| `collect_nvidia_smi` | Return structured GPU telemetry. |
| `collect_service_status` | Return status for allowlisted services only. |

Each action should require:

- explicit backend route
- strict confirmation in the UI
- idempotency key
- allowlisted target
- durable `Run` record
- timeout and terminal status

## Explicit Non-Goals

The local node agent must not expose:

- arbitrary command execution
- unrestricted file reads or writes
- unrestricted service management
- unauthenticated endpoints in shared deployments
- browser-facing credentials

## Deployment Model

Recommended systemd shape:

```text
Backend container -> HTTP bearer auth -> local node agent -> allowlisted host action
```

The backend continues to run in Docker. The local agent runs as a dedicated system user through systemd. Any future host remediation should happen through this boundary, not by expanding backend container privileges.

## Packaging Status

This is a planned extension point, not an enabled host-control feature. The current release packaging includes the generic agent installer under `deploy/agent/`, which is suitable for local or remote telemetry. Host-level remediation actions should be added only after their action contracts, security boundaries, and tests are explicit.
