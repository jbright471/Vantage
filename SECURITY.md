# Security

Vantage is designed as a local-first control plane for private AI infrastructure.

## Security Posture

- Vantage is intended for trusted LAN or VPN environments.
- Telemetry and model operations stay local to the operator's network.
- The backend stores operational state in local SQLite.
- The remote agent supports bearer-token authentication for node-to-node communication.
- Secrets are supplied through environment files and are ignored by git.

## Agent Authentication

The Bastet agent reads:

```text
VANTAGE_AGENT_SHARED_TOKEN
```

When configured, all agent endpoints require:

```http
Authorization: Bearer <token>
```

The Jedi backend sends this header when the same environment variable is available to the backend container.

Local files:

- `.env`: local backend/container secret file, ignored by git
- `/opt/vantage/vantage-agent.env`: remote agent secret file on Bastet
- `.env.example`: committed example with no secret value

## Local-First Data Handling

Vantage does not require cloud services for Phase 1 operation.

The app currently observes:

- node health
- GPU telemetry
- Ollama model inventory
- routing preferences
- run history and capability-check metadata

Operators should avoid putting sensitive prompts or private data into capability-check prompts unless the selected local model and machine are trusted.

## Network Exposure

Recommended deployment posture:

- expose the UI only on a trusted LAN or VPN
- keep the backend off the public internet
- keep remote agent ports reachable only from the control plane
- use host firewall rules where practical
- rotate `VANTAGE_AGENT_SHARED_TOKEN` after accidental disclosure

## Known Limitations

- Vantage does not currently provide human user accounts or browser login.
- Agent authentication is shared-secret based, not mutual TLS.
- The development Compose file is not hardened for internet exposure.
- SQLite is local and not encrypted by Vantage.

## Reporting Vulnerabilities

For now, report security issues privately to the repository owner rather than opening a public issue.

Please include:

- affected endpoint or component
- reproduction steps
- expected impact
- relevant logs with secrets removed
- suggested remediation, if known

Do not include live tokens, private prompts, or model output containing sensitive data in reports.

## Secret Handling Rules

- Never commit `.env` or `vantage-agent.env`.
- Do not paste live tokens into issues, PRs, or docs.
- Rotate tokens after disclosure.
- Prefer generated high-entropy tokens, for example:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
