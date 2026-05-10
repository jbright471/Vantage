# Security

Vantage is designed as a local-first control plane for private AI infrastructure.

The examples below use `jedi` as an example control-plane node name and `bastet` as an example remote worker node name. Replace them with names from your own homelab.

## Security Posture

- Vantage is intended for trusted LAN or VPN environments.
- Telemetry and model operations stay local to the operator's network.
- The backend stores operational state in local SQLite.
- The remote agent supports bearer-token authentication by default and optional HMAC request signing with replay protection.
- Signed audit bundles can make exported run history tamper-evident when `VANTAGE_AUDIT_SIGNING_KEY` is configured.
- Integration endpoints can be protected with `VANTAGE_EXTERNAL_API_TOKEN` before connecting n8n, scripts, or webhook receivers.
- Secrets are supplied through environment files and are ignored by git.
- Production Compose requires `VANTAGE_AGENT_SHARED_TOKEN` to be supplied externally before startup.
- Demo mode uses synthetic data and is the recommended way to create public screenshots or reproduction steps.

## Agent Authentication

The remote agent reads this environment variable. For example, an operator might run it on a worker node named `bastet`:

```text
VANTAGE_AGENT_SHARED_TOKEN
```

Bearer mode is the default. When configured, all agent endpoints require:

```http
Authorization: Bearer <token>
```

The control-plane backend sends this header when the same environment variable is available to the backend container. For example, an operator might run the backend on a node named `jedi`.

For stronger node-to-node trust, set:

```text
VANTAGE_AGENT_AUTH_MODE=hmac
VANTAGE_AGENT_KEY_ID=<optional-key-id>
VANTAGE_AGENT_ALLOWED_ACTIONS=read,capability_check,eval_attempt
```

HMAC mode signs each request with timestamp, nonce, path, method, and body hash headers. The agent rejects stale timestamps and replayed nonces. Use `bearer_or_hmac` only as a short migration state during token/auth-mode changes.

Local files:

- `.env`: local backend/container secret file, ignored by git
- `/opt/vantage/vantage-agent.env`: remote agent secret file on the worker node
- `.env.example`: committed example with no secret value
- `.env.production.example`: committed production example with no secret value

Production Compose refuses to start without `VANTAGE_AGENT_SHARED_TOKEN`. Use `--env-file .env.production`, Portainer secrets, or Portainer environment variables to supply the token outside the Compose YAML.

## Audit Export Signing

Signed run-history bundles are available at:

```text
/api/runs/export.bundle.json
```

They require:

```text
VANTAGE_AUDIT_SIGNING_KEY
VANTAGE_AUDIT_KEY_ID
```

The bundle includes canonical payload metadata, a SHA-256 payload digest, and an HMAC-SHA256 signature. Keep the signing key separate from exported bundles. See `docs/security/AUDIT_EXPORTS.md`.

## Local-First Data Handling

Vantage does not require cloud services for current local-first operation.

The app currently observes:

- node health
- GPU telemetry
- Ollama model inventory
- routing preferences
- run history and capability-check metadata

Operators should avoid putting sensitive prompts or private data into capability-check prompts unless the selected local model and machine are trusted.

## Release Artifact Hygiene

Release bundles are designed to be shareable. They should include public-safe examples and exclude:

- `.env`
- `.env.production`
- `vantage.sqlite3`
- local logs
- node modules
- machine-specific bootstrap config values

Before publishing a release, inspect the generated zip for populated tokens, private IPs, local filesystem paths, and accidental database files.

Use `VANTAGE_DEMO_MODE=1` for public release screenshots and walkthroughs. Do not publish screenshots taken from real production state unless node names, base URLs, prompts, run metadata, and local paths have been redacted.

## Network Exposure

Recommended deployment posture:

- expose the UI only on a trusted LAN or VPN
- keep the backend off the public internet
- keep remote agent ports reachable only from the control plane
- use host firewall rules where practical
- rotate `VANTAGE_AGENT_SHARED_TOKEN` after accidental disclosure
- use HMAC mode when replay protection is required
- set `VANTAGE_EXTERNAL_API_TOKEN` before exposing `/api/integrations/*`
- restrict webhook targets with `VANTAGE_WEBHOOK_ALLOWED_HOSTS` when using dispatch endpoints

## Known Limitations

- Vantage does not currently provide human user accounts or browser login.
- Agent authentication is shared-secret based; HMAC mode adds request signing and replay protection but is not mutual TLS.
- The development Compose file is not hardened for internet exposure.
- The production Compose file improves packaging posture but still assumes trusted LAN or VPN access.
- SQLite is local and not encrypted by Vantage.
- Optional host-level remediation must go through a future local node agent with explicit allowlists, not a privileged backend container.

## Reporting Vulnerabilities

Report security issues privately to the repository owner rather than opening a public issue. If the GitHub repository is public, use the repository security policy or private vulnerability reporting when available.

Please include:

- affected endpoint or component
- reproduction steps
- expected impact
- relevant logs with secrets removed
- suggested remediation, if known

Do not include live tokens, private prompts, or model output containing sensitive data in reports.

## Secret Handling Rules

- Never commit `.env` or `vantage-agent.env`.
- Never commit `.env.production`.
- Do not paste live tokens into issues, PRs, or docs.
- Rotate tokens after disclosure.
- Use `scripts/rotate-agent-token.ps1` for a dry-run or applied token rotation workflow.
- Prefer generated high-entropy tokens, for example:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
