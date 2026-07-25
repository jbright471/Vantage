# Vantage

Vantage is a local-first AI control plane for operators running private models across multiple machines.

It gives you one place to watch node health, GPU telemetry, model placement, routing policy, and run history while preserving the independence of the systems it observes.

## Why Vantage Exists

Local AI setups grow sideways fast: one machine becomes two, one Ollama endpoint becomes a router, scheduled jobs start running in the background, and suddenly "what is actually happening right now?" becomes hard to answer.

Vantage exists to make that state visible and actionable without taking ownership of the underlying services.

## Design Principles

- `Observer, not replacer`: Vantage sits above existing services such as Ollama, routers, schedulers, and node agents. Those systems should keep working if Vantage is down.
- `Truth over appearance`: stale, degraded, and unreachable states are shown directly instead of being hidden behind optimistic UI.
- `Freshness is first-class`: live state and last-known state are separated everywhere possible.
- `Every action is auditable`: operator actions and model checks become durable `Run` records.
- `Local-first by default`: telemetry, run history, and model operations stay on your own network.

## Features

- Live node health for local and remote machines
- Attention ribbon and warning strip for stale, degraded, and drift states
- Eval schedule health warnings for failed auto-executed prompt suites
- Heartbeat freshness meters with visual decay
- Node diagnostics with observed errors and suggested remediation
- Verified node refresh remediation with durable action results
- Node quarantine and re-enable actions with strict confirmation
- Local Ollama endpoint disable actions for known-bad endpoints across polling, capability checks, and eval execution
- Warning acknowledgement with durable audit records
- GPU telemetry from remote Linux workers
- Merged model inventory across nodes
- Model placement details with Ollama digests
- Operator-editable routing policy lanes with model-specific rules, dry-run simulation, failover flags, route history, and strict override confirmation
- Remote run ingestion from node agents
- Backend-filtered run history with pagination
- CSV, JSON, and signed bundle audit exports for run history, plus a CLI verification helper
- Local LLM capability checks from the Models surface
- Eval Lab for prompt suites, executable eval runs, richer score types including guided guarded local-LLM judge configs, placement comparison, baseline regression checks, configurable intelligence windows, managed scope presets, trend summaries, flakiness detection, failure clustering, manual local-LLM assisted summaries, recurring schedules, suite import/export, lifecycle cleanup, and opt-in auto-execution
- SSE-based live UI updates
- SQLite persistence with bounded snapshot pruning, plus optional non-SQLite SQLAlchemy URLs for Postgres-backed deployments
- Shared-token authentication for node agents with optional HMAC request signing and replay protection
- Deployment health endpoints for liveness and readiness checks
- Structured JSON backend logs for container and service supervisors
- Docker Compose development environment
- Production Compose profile with Alembic migrations and persisted SQLite volume
- Portainer deployment guide, setup checker, bounded Docker log rotation, and SQLite backup/restore guidance
- First-class GitHub release bundle workflow with SHA256 checksums
- Optional local node-agent boundary for future host-level remediation
- Generic systemd installer for remote Linux agents
- Demo mode with public-safe synthetic nodes, runs, models, evals, warnings, and routing policies
- First-run onboarding checklist in the web UI
- First-run setup wizard for token, node registry, local Ollama, and verification snippets
- Public product microsite and install walkthrough assets
- Integration API for n8n/scripts with event export, webhook and SMTP email dispatch, router-log import, scheduled Markdown reports, integration health, security-event counters, and collector discovery
- GitHub Pages-ready product documentation and a Remotion-ready walkthrough video scaffold

## Quick Start

From the repository root:

Run the public-safe demo first. Demo mode seeds synthetic nodes, models, runs, warnings, routing policies, and eval history so you can evaluate the UI without exposing or configuring real infrastructure.

```powershell
Copy-Item .env.example .env
.\scripts\rotate-agent-token.ps1 -EnvFile .env -Apply
.\scripts\rotate-control-plane-secrets.ps1 -EnvFile .env -Apply
(Get-Content .env) -replace '^VANTAGE_DEMO_MODE=.*', "VANTAGE_DEMO_MODE=1" | Set-Content .env
docker compose up --build -d
```

Open:

- UI: [http://127.0.0.1:5173](http://127.0.0.1:5173)
- Backend API: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Backend readiness: [http://127.0.0.1:8000/api/health/ready](http://127.0.0.1:8000/api/health/ready)

The UI prompts for `VANTAGE_CONTROL_PLANE_TOKEN`. Copy it to the clipboard without displaying it:

```powershell
((Get-Content .env | Where-Object { $_ -like 'VANTAGE_CONTROL_PLANE_TOKEN=*' }) -split '=', 2)[1] | Set-Clipboard
```

Useful commands:

```powershell
docker compose ps
docker compose logs -f
Invoke-RestMethod http://127.0.0.1:8000/api/health/ready
docker compose down
```

When you are ready to connect real nodes, turn demo mode off, edit [config/vantage.bootstrap.toml](./config/vantage.bootstrap.toml), and enable the remote workers you want Vantage to poll:

```powershell
(Get-Content .env) -replace '^VANTAGE_DEMO_MODE=.*', "VANTAGE_DEMO_MODE=0" | Set-Content .env
docker compose up --build -d
```

Production-style Compose:

```powershell
Copy-Item .env.production.example .env.production
.\scripts\rotate-agent-token.ps1 -EnvFile .env.production -Apply
.\scripts\rotate-control-plane-secrets.ps1 -EnvFile .env.production -Apply
docker compose -f docker-compose.prod.yml --env-file .env.production up --build -d
Invoke-RestMethod http://127.0.0.1:5173/api/health/ready
```

Production Compose publishes only the frontend, bound to `127.0.0.1` by default; the backend remains on the internal Compose network. Set `VANTAGE_BIND_ADDRESS` to a specific trusted LAN/VPN interface only when remote access is required.

## Configuration

Primary bootstrap config lives at [config/vantage.bootstrap.toml](./config/vantage.bootstrap.toml). The tracked default is public-safe: it enables only the local control-plane node and includes a disabled `remote-worker` example that you can rename, point at your own agent URL, and enable when ready.

| Setting | Purpose | Default |
| --- | --- | --- |
| `poll_interval_seconds` | Backend polling cadence | `5` |
| `stale_after_seconds` | Marks observed state as stale | `15` |
| `unreachable_after_seconds` | Marks stale nodes unreachable | `30` |
| `snapshot_retention_hours` | Age-based snapshot pruning | `24` |
| `snapshot_max_per_node` | Count cap per node | `5000` |
| `snapshot_min_per_node` | Minimum retained snapshots per node | `1` |
| `snapshot_prune_interval_seconds` | Background snapshot pruning cadence | `900` |
| `eval_schedule_interval_seconds` | Background due-schedule check cadence | `60` |
| `report_schedule_interval_seconds` | Optional scheduled report worker cadence | `3600` |
| `agent_auth_token_env` | Env var used for agent bearer auth | `VANTAGE_AGENT_SHARED_TOKEN` |

Local secrets belong in `.env`, which is ignored by git. See [.env.example](./.env.example).

Production secrets belong in `.env.production`, which is also ignored by git. See [.env.production.example](./.env.production.example). Public-safe bootstrap defaults live at [config/vantage.bootstrap.example.toml](./config/vantage.bootstrap.example.toml).

Signed audit bundles require `VANTAGE_AUDIT_SIGNING_KEY`. Stronger node-agent trust can be enabled with `VANTAGE_AGENT_AUTH_MODE=hmac`; see [Agent Authentication](./docs/security/AGENT_AUTH.md).

## Documentation

- [Architecture](./ARCHITECTURE.md)
- [Roadmap](./ROADMAP.md)
- [Getting Started](./GETTING_STARTED.md)
- [Operator Guide](./OPERATOR_GUIDE.md)
- [Product Microsite](./docs/product/index.html)
- [Install Walkthrough Script](./docs/walkthrough/INSTALL_WALKTHROUGH.md)
- [Walkthrough Video Plan](./docs/walkthrough/video/README.md)
- [Remote Agent Contract](./AGENT_CONTRACT.md)
- [Agent Authentication](./docs/security/AGENT_AUTH.md)
- [Audit Exports](./docs/security/AUDIT_EXPORTS.md)
- [Action Idempotency Keys](./docs/security/IDEMPOTENCY_KEYS.md)
- [Release Security Checklist](./docs/security/RELEASE_SECURITY_CHECKLIST.md)
- [Security Audit](./SECURITY_AUDIT.md)
- [Threat Model](./docs/security/THREAT_MODEL.md)
- [Single-operator Authentication ADR](./docs/architecture/ADR-001-single-operator-authentication.md)
- [mTLS Research](./docs/security/MTLS_RESEARCH.md)
- [Integrations](./docs/integrations/INTEGRATIONS.md)
- [n8n Examples](./docs/integrations/N8N_EXAMPLES.md)
- [Collector Plugins](./docs/integrations/COLLECTOR_PLUGINS.md)
- [Operations](./OPERATIONS.md)
- [Portainer Deployment](./PORTAINER.md)
- [Release Packaging](./RELEASE.md)
- [Optional Local Node Agent](./LOCAL_NODE_AGENT.md)
- [Screenshot Guide](./SCREENSHOTS.md)
- [Public Screenshots](./docs/screenshots)
- [Changelog](./CHANGELOG.md)
- [Security](./SECURITY.md)
- [Contributing](./CONTRIBUTING.md)
- [Support](./SUPPORT.md)

## Project Status

Vantage v0.1.0 ships the control-plane foundation, operator attention, diagnostics, guided remediation, Eval Lab, Eval Intelligence, advanced local-LLM judge foundations, routing-policy control, production packaging, demo mode, setup wizard, public product assets, open-source onboarding materials, signed audit bundles, optional HMAC agent authentication, replay protection, action allowlists, security-warning surfacing, managed eval presets, integration health, email/report automation, and local-first integration endpoints. The current version is useful for a single local AI operator and remains intentionally conservative about distributed control and host-level remediation.

The unreleased tree adds fail-closed operator sessions, CSRF protection, resource limits, non-root containers, hardened network defaults, automated security scanning, SBOM generation, and the evidence-backed release gates documented in [SECURITY_AUDIT.md](./SECURITY_AUDIT.md).

Later Research decisions are tracked in `docs/architecture/LATER_RESEARCH_DECISIONS.md`. SQLite remains the default database, but `VANTAGE_DATABASE_URL` can now point at a non-SQLite SQLAlchemy URL when an operator wants to experiment with Postgres-backed storage.

## License

Vantage is released under the [MIT License](./LICENSE).
