# Portainer Deployment Guide

This guide deploys Vantage as a production-style Portainer stack on a trusted LAN or VPN.

The examples use generic hostnames and addresses. Replace `<control-plane-host>`, `<remote-agent-ip>`, and node names with values from your own homelab.

## What Portainer Runs

Use [docker-compose.prod.yml](./docker-compose.prod.yml). The production stack:

- builds an immutable FastAPI backend image
- runs `alembic upgrade head` before backend startup
- stores SQLite in the `vantage_data` volume
- includes the Postgres driver so `VANTAGE_DATABASE_URL` can point at Postgres when needed
- serves the React frontend through Nginx
- proxies `/api` and SSE traffic from frontend to backend
- applies backend and frontend health checks
- rotates Docker JSON logs with a bounded size

## Prerequisites

- Portainer connected to a Docker host
- Git repository or release bundle available to the Docker host
- Trusted LAN or VPN access only
- A generated `VANTAGE_AGENT_SHARED_TOKEN`
- Remote worker agents reachable from the control-plane host

Generate a token:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Environment Variables

Create Portainer stack environment variables or secrets:

| Variable | Required | Purpose |
| --- | --- | --- |
| `VANTAGE_AGENT_SHARED_TOKEN` | Yes | Shared token used between backend and agents. |
| `VANTAGE_AGENT_AUTH_MODE` | No | `bearer` by default; use `hmac` for signed requests and replay protection. |
| `VANTAGE_AGENT_ALLOWED_ACTIONS` | No | Agent allowlist. Default: `read,capability_check,eval_attempt`. |
| `VANTAGE_AUDIT_SIGNING_KEY` | No | Required only for signed audit bundle exports. |
| `VANTAGE_AUDIT_KEY_ID` | No | Operator-readable key ID written into signed audit bundle metadata. |
| `VANTAGE_EXTERNAL_API_TOKEN` | No | Protects `/api/integrations/*` for n8n, scripts, and external tools. |
| `VANTAGE_WEBHOOK_URL` | No | Generic webhook target for integration dispatch. |
| `VANTAGE_SLACK_WEBHOOK_URL` | No | Slack-compatible webhook target. |
| `VANTAGE_DISCORD_WEBHOOK_URL` | No | Discord-compatible webhook target. |
| `VANTAGE_WEBHOOK_ALLOWED_HOSTS` | No | Optional comma-separated hostname allowlist for webhook dispatch. |
| `VANTAGE_LOCAL_OLLAMA_BASE_URLS` | No | Comma-separated local Ollama endpoints reachable from the backend container. |
| `VANTAGE_DATABASE_URL` | No | Overrides the default SQLite location. Production Compose defaults to `sqlite+pysqlite:////data/vantage.sqlite3`; Postgres URLs can use `postgresql+psycopg://...`. |

Do not paste real tokens or audit signing keys into the Compose file, docs, screenshots, or GitHub issues.

If you use Portainer secrets, confirm the resolved environment is visible to the backend container before starting the stack. Vantage treats missing `VANTAGE_AGENT_SHARED_TOKEN` as a production startup error in `docker-compose.prod.yml`.

## Bootstrap Config

Edit `config/vantage.bootstrap.toml` before deploying, or mount your own config file into the backend image in a future custom stack.

For a public-safe starting point, copy:

```text
config/vantage.bootstrap.example.toml
```

to:

```text
config/vantage.bootstrap.toml
```

Then replace:

- `control-plane` with your control-plane node ID
- `remote-worker` with your worker node ID
- `http://<remote-agent-ip>:9110` with the worker agent URL

## Stack Creation

1. Open Portainer.
2. Go to `Stacks`.
3. Choose `Add stack`.
4. Name the stack `vantage`.
5. Paste or reference [docker-compose.prod.yml](./docker-compose.prod.yml).
6. Add the required environment variables.
7. Deploy the stack.

## Verification

From an operator workstation:

```powershell
Invoke-RestMethod http://<control-plane-host>:8000/api/health/live
Invoke-RestMethod http://<control-plane-host>:8000/api/health/ready
```

Open the UI:

```text
http://<control-plane-host>:5173
```

In Portainer, confirm:

- backend container is `healthy`
- frontend container is `healthy`
- backend logs show JSON records
- no startup migration errors appear
- the Docs drawer loads the Operator Guide from `/api/docs/operator-guide.md`

## Updating

1. Back up SQLite before updating.
2. Pull the new release bundle or repository revision.
3. Review `ROADMAP.md`, `OPERATIONS.md`, and migration notes.
4. Re-deploy the stack in Portainer.
5. Watch backend logs while Alembic runs.
6. Verify `/api/health/ready`.
7. Open the UI and confirm Nodes, Runs, Models, Routing, and Evals load.

If you run Postgres instead of SQLite, use your Postgres backup and restore workflow instead of the SQLite backup steps. Postgres enables stronger database operations, but it does not by itself make multiple active Vantage control planes safe.

## Rollback

Rollback quickly if readiness fails, migrations fail, or the UI cannot reach the backend.

1. Stop the stack.
2. Restore the previous release bundle or image tag.
3. Restore the SQLite backup if the failed deployment ran migrations.
4. Start the stack.
5. Verify `/api/health/ready`.

## Logs

The production Compose file uses Docker's `json-file` logging driver with:

```yaml
max-size: "10m"
max-file: "5"
```

This prevents container logs from growing indefinitely on small homelab disks. For longer retention, forward Docker logs to your existing logging stack instead of increasing local log files without a retention plan.

## Remote Agents

Install the remote agent on each Linux worker:

```bash
sudo VANTAGE_AGENT_SHARED_TOKEN="<same-token-as-control-plane>" \
  VANTAGE_AGENT_NODE_ID="<your-node-id>" \
  VANTAGE_AGENT_OLLAMA_BASE_URLS="http://127.0.0.1:11434" \
  bash deploy/agent/install.sh
```

Verify from the control-plane host:

```powershell
$token = "<same-token-as-control-plane>"
Invoke-RestMethod http://<remote-agent-ip>:9110/health -Headers @{ Authorization = "Bearer $token" }
```

## Preflight Check

Run the setup checker before or after deployment:

```powershell
$env:VANTAGE_AGENT_SHARED_TOKEN = "<same-token-as-control-plane>"
.\scripts\check-setup.ps1 `
  -ComposeFile docker-compose.prod.yml `
  -RemoteAgentUrl http://<remote-agent-ip>:9110 `
  -ControlPlaneUrl http://<control-plane-host>:8000
```
