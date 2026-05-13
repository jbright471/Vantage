# Operations

This guide covers running Vantage locally with Docker Compose and deploying the lightweight remote agent to Linux worker nodes.

The examples below use `control-plane` as an example control-plane node name and `remote-worker` as an example remote worker node name. Replace them with names from your own homelab.

## Local Development

Requirements:

- Docker Desktop with WSL2 enabled on Windows
- Git
- Existing local Ollama endpoints if you want live model inventory

Create a local token file:

```powershell
$token = python -c "import secrets; print(secrets.token_urlsafe(48))"
(Get-Content .env.example) -replace '^VANTAGE_AGENT_SHARED_TOKEN=.*', "VANTAGE_AGENT_SHARED_TOKEN=$token" | Set-Content .env
```

Start the stack:

```powershell
docker compose up --build -d
```

Open:

- UI: [http://127.0.0.1:5173](http://127.0.0.1:5173)
- API: [http://127.0.0.1:8000](http://127.0.0.1:8000)

Watch logs:

```powershell
docker compose logs -f
```

Check health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health/live
Invoke-RestMethod http://127.0.0.1:8000/api/health/ready
```

Stop:

```powershell
docker compose down
```

## Production Direction

The current `docker-compose.yml` is development-oriented. It mounts local source directories into containers so FastAPI reload and Vite HMR stay fast.

Use [docker-compose.prod.yml](./docker-compose.prod.yml) for a production-style deployment through Portainer or another Compose host. It builds immutable backend and frontend images, persists SQLite to a named volume, runs Alembic migrations before the backend starts, serves the frontend through Nginx, and wires container health checks.

Before starting production Compose, set a shared token:

```powershell
$env:VANTAGE_AGENT_SHARED_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(48))"
docker compose -f docker-compose.prod.yml up --build -d
```

If you need signed audit bundles, also set:

```powershell
$env:VANTAGE_AUDIT_SIGNING_KEY = python -c "import secrets; print(secrets.token_urlsafe(48))"
$env:VANTAGE_AUDIT_KEY_ID = "production-audit-key"
```

If you keep production values in a file, copy [.env.production.example](./.env.production.example) to `.env.production`, fill in real values, and run:

```powershell
docker compose -f docker-compose.prod.yml --env-file .env.production up --build -d
```

`.env.production` is ignored by git. Keep real tokens out of Compose YAML, screenshots, tickets, and docs.

Production posture:

- do not mount source code into containers
- persist `vantage.sqlite3` to the `vantage_data` volume or configure `VANTAGE_DATABASE_URL` for an external Postgres database
- provide `VANTAGE_AGENT_SHARED_TOKEN` as a secret or environment variable, not in the Compose file
- use `VANTAGE_AGENT_AUTH_MODE=hmac` when request signing and replay protection are required
- provide `VANTAGE_AUDIT_SIGNING_KEY` when signed run-history bundles are part of your audit process
- set `VANTAGE_EXTERNAL_API_TOKEN` before exposing integration endpoints to n8n, scripts, or other automation
- keep `VANTAGE_DEMO_MODE=0` unless intentionally running a public demo or screenshot instance
- expose the frontend only to trusted LAN users
- keep the backend reachable only from the frontend and trusted operator machines
- use `/api/health/ready` as the backend deployment gate

## Portainer Deployment Sketch

See [PORTAINER.md](./PORTAINER.md) for the full deployment guide.

Short version:

1. Push the Vantage repository, release bundle, or built images to a location your Portainer host can reach.
2. Create a Portainer stack from `docker-compose.prod.yml`.
3. Set `VANTAGE_AGENT_SHARED_TOKEN` in Portainer environment variables or secrets.
4. Mount persistent storage for SQLite, or configure an external Postgres URL.
5. Start the stack and confirm:

```powershell
Invoke-RestMethod http://<host>:8000/api/health/live
Invoke-RestMethod http://<host>:8000/api/health/ready
```

6. Open the UI at:

```text
http://<host>:5173
```

## Setup Checks

Use [scripts/check-setup.ps1](./scripts/check-setup.ps1) to validate the local deployment surface before trusting a stack:

```powershell
$env:VANTAGE_AGENT_SHARED_TOKEN = "<same-token-as-control-plane>"
.\scripts\check-setup.ps1 `
  -ComposeFile docker-compose.prod.yml `
  -RemoteAgentUrl http://<remote-agent-ip>:9110 `
  -ControlPlaneUrl http://<control-plane-host>:8000
```

The check covers Docker availability, Compose configuration, token presence, auth mode, optional audit signing key, bootstrap config presence, optional SQLite path parent directory, backend readiness, and remote-agent reachability.

SQLite remains the default database. If you set `VANTAGE_DATABASE_URL=postgresql+psycopg://...`, use your Postgres backup and monitoring workflow and remember that Postgres alone does not make multiple active control planes safe.

## Integrations And Automation

Vantage exposes local-first integration endpoints under `/api/integrations/*`. They are intended for n8n, cron scripts, local webhook receivers, and incident-note exports.

Recommended production environment:

```text
VANTAGE_EXTERNAL_API_TOKEN=<generated-token>
VANTAGE_WEBHOOK_URL=http://<automation-host>:<port>/<path>
VANTAGE_WEBHOOK_ALLOWED_HOSTS=<automation-host>
VANTAGE_EMAIL_SMTP_HOST=<smtp-host>
VANTAGE_EMAIL_SMTP_PORT=587
VANTAGE_EMAIL_SMTP_USERNAME=<smtp-user>
VANTAGE_EMAIL_SMTP_PASSWORD=<smtp-password>
VANTAGE_EMAIL_FROM=vantage@<your-domain>
VANTAGE_EMAIL_TO=operator@<your-domain>
VANTAGE_EMAIL_USE_TLS=1
```

Common checks:

```powershell
Invoke-RestMethod http://<control-plane-host>:8000/api/integrations/events `
  -Headers @{ "X-Vantage-Api-Key" = "<external-api-token>" }

Invoke-RestMethod http://<control-plane-host>:8000/api/integrations/reports/operator.md `
  -Headers @{ "X-Vantage-Api-Key" = "<external-api-token>" }
```

Use [docs/integrations/N8N_EXAMPLES.md](./docs/integrations/N8N_EXAMPLES.md) for scheduled pulls, webhook dispatch, router-log import, and Markdown report export examples.

If you do not use n8n or cron, enable the built-in report worker:

```text
VANTAGE_REPORT_SCHEDULE_ENABLED=1
VANTAGE_REPORT_OUTPUT_DIR=/data/reports
```

The worker writes Markdown reports on the cadence set by `report_schedule_interval_seconds`.

Check integration health from the UI panel or API:

```powershell
Invoke-RestMethod http://<control-plane-host>:8000/api/integrations/health
```

## Token Rotation

Generate a replacement agent token without changing files:

```powershell
.\scripts\rotate-agent-token.ps1
```

Apply a new token to `.env.production`:

```powershell
.\scripts\rotate-agent-token.ps1 -EnvFile .env.production -Apply
```

Then copy the same value into each remote agent env file, restart the backend, restart every `vantage-agent` service, and verify node health. If you use `VANTAGE_AGENT_AUTH_MODE=bearer_or_hmac` during migration, return to `bearer` or `hmac` once all nodes are aligned.

## Remote Linux Agent

The remote agent is a FastAPI service managed by systemd.

Generic service file path:

```text
deploy/agent/vantage-agent.service
```

Default port:

```text
9110
```

### Install On A Worker Node

Copy the repository, release bundle, or `agent/` plus `deploy/agent/` files onto the worker node. From the repository root on the worker:

```bash
sudo VANTAGE_AGENT_SHARED_TOKEN="<same-token-as-control-plane>" \
  VANTAGE_AGENT_NODE_ID="<your-node-id>" \
  VANTAGE_AGENT_OLLAMA_BASE_URLS="http://127.0.0.1:11434" \
  bash deploy/agent/install.sh
```

The installer creates:

- `/opt/vantage/agent`
- `/opt/vantage/.venv`
- `/opt/vantage/vantage-agent.env`
- `/etc/systemd/system/vantage-agent.service`

Set `VANTAGE_AGENT_NODE_ID` to the same node ID used in `config/vantage.bootstrap.toml`. If you need a custom install path, set `VANTAGE_INSTALL_DIR`. If you need a custom service user, set `VANTAGE_AGENT_USER`.

Check status:

```bash
systemctl status vantage-agent --no-pager
```

## Agent Verification

Unauthenticated requests should fail:

```powershell
Invoke-WebRequest http://<remote-agent-ip>:9110/health -SkipHttpErrorCheck
```

Authenticated requests should pass:

```powershell
$token = (Get-Content .env | Where-Object { $_ -like 'VANTAGE_AGENT_SHARED_TOKEN=*' }).Split('=',2)[1]
Invoke-RestMethod http://<remote-agent-ip>:9110/health -Headers @{ Authorization = "Bearer $token" }
```

The control plane should show the node as healthy:

```powershell
Invoke-RestMethod http://<control-plane-host>:8000/api/nodes
```

## Health Checks And Logs

The control-plane backend exposes three health endpoints:

| Endpoint | Purpose | Dependency Level |
| --- | --- | --- |
| `/api/health` | Backward-compatible basic status check. | Process only |
| `/api/health/live` | Liveness check for container or service supervisors. | Process only |
| `/api/health/ready` | Readiness check before trusting the UI or routing traffic. | Database, required tables, bootstrap config |

Use `/api/health/live` for restart decisions. Use `/api/health/ready` for deployment verification and load-gate checks. A readiness failure returns HTTP `503` and identifies the failed check without exposing secrets, local filesystem paths, or private network configuration.

For public demos, set `VANTAGE_DEMO_MODE=1` and prefer `VANTAGE_ENABLE_BACKGROUND_POLLING=0` so screenshots stay on synthetic state. The setup checker warns if demo mode is enabled during production verification.

Backend logs are emitted as JSON to stdout so Docker, Portainer, systemd, or a future log collector can ingest them consistently. Each record includes a timestamp, log level, logger name, message, and exception details when present.

Production Compose rotates Docker JSON logs using:

```yaml
max-size: "10m"
max-file: "5"
```

For Portainer, inspect container logs during deployment and configure host-level Docker log retention if you override the Compose logging options.

For systemd-managed agents, read logs with:

```bash
journalctl -u vantage-agent -f
```

The service uses `SyslogIdentifier=vantage-agent` so entries are easy to filter. Journald retention is controlled by the host's `/etc/systemd/journald.conf`, commonly through `SystemMaxUse`, `RuntimeMaxUse`, and `MaxRetentionSec`.

## Database Protection

Snapshot pruning is automatic during the backend polling loop.

Current defaults:

- keep snapshots for `24` hours
- keep at most `5000` snapshots per node
- keep at least `1` snapshot per node

Tune these in [config/vantage.bootstrap.toml](./config/vantage.bootstrap.toml).

## Database Backup And Restore

SQLite backups should use the SQLite backup API instead of copying the database file while the backend may be writing.

Create a backup from the host path or extracted volume file:

```powershell
$source = "vantage.sqlite3"
$target = "backups/vantage-$(Get-Date -Format yyyyMMdd-HHmmss).sqlite3"
New-Item -ItemType Directory -Force backups | Out-Null
python -c "import sqlite3, sys; src=sqlite3.connect(sys.argv[1]); dst=sqlite3.connect(sys.argv[2]); src.backup(dst); src.close(); dst.close()" $source $target
```

Restore only while the backend is stopped:

```powershell
docker compose -f docker-compose.prod.yml stop backend
Copy-Item backups/<backup-file>.sqlite3 <database-path-or-mounted-volume-file> -Force
docker compose -f docker-compose.prod.yml start backend
Invoke-RestMethod http://<host>:8000/api/health/ready
```

For always-on deployments, evaluate Litestream or another WAL-aware backup tool once Vantage is running continuously.

## Alembic Migrations

Production images run `python -m alembic upgrade head` before starting the backend.

For a new database, migrations create the schema before FastAPI starts. For an existing pre-Alembic database, take a SQLite backup first, then stamp the current schema:

```powershell
python -m alembic stamp head
```

When changing SQLAlchemy models:

```powershell
python -m alembic revision --autogenerate -m "describe schema change"
python -m alembic upgrade head
python -m pytest tests/backend -q
```

Always review generated migrations before committing them. SQLite table rewrites should use Alembic batch mode, which is enabled in `migrations/env.py`.

## Optional Local Node Agent

See [LOCAL_NODE_AGENT.md](./LOCAL_NODE_AGENT.md).

The short rule: do not make the Docker backend privileged just to restart host services or collect low-level hardware data. If Vantage needs host-level remediation on the control-plane machine, install a local systemd-managed agent and expose only narrow, allowlisted actions through authenticated HTTP.

## Release Artifacts

See [RELEASE.md](./RELEASE.md).

Build a local release bundle:

```powershell
.\scripts\build-release.ps1 -Version v0.1.0
```

The bundle is written to `dist/releases/` with a matching `SHA256SUMS.txt`. GitHub Actions also builds and uploads the same artifacts when a `v*` tag is pushed.

Verify a signed audit bundle:

```powershell
$env:VANTAGE_AUDIT_SIGNING_KEY = "<same-secret-used-to-sign>"
python scripts/verify-audit-bundle.py <path-to-bundle.json>
```
