# Getting Started

This guide is for operators evaluating Vantage from a fresh clone.

## Fastest Path: Demo Mode

Demo mode seeds safe synthetic data so you can inspect the UI, exports, routing, evals, and warnings before connecting real hardware.

```powershell
Copy-Item .env.example .env
.\scripts\rotate-agent-token.ps1 -EnvFile .env -Apply
.\scripts\rotate-control-plane-secrets.ps1 -EnvFile .env -Apply -IncludeAuditSigningKey
(Get-Content .env) -replace '^VANTAGE_DEMO_MODE=.*', "VANTAGE_DEMO_MODE=1" | Set-Content .env
docker compose up --build -d
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173).

The browser prompts for the operator token. Copy it to the clipboard without printing it to the terminal:

```powershell
((Get-Content .env | Where-Object { $_ -like 'VANTAGE_CONTROL_PLANE_TOKEN=*' }) -split '=', 2)[1] | Set-Clipboard
```

Vantage exchanges the token for a signed, HttpOnly browser session. The token is not stored in browser local storage.

If you want a frozen demo without live polling, also set:

```powershell
Add-Content .env "VANTAGE_ENABLE_BACKGROUND_POLLING=0"
```

## Connect Real Nodes

1. Copy `config/vantage.bootstrap.example.toml` to the ignored `config/vantage.bootstrap.local.toml`, then set `VANTAGE_BOOTSTRAP_CONFIG_PATH=/app/config/vantage.bootstrap.local.toml` in `.env`. This keeps private hostnames and LAN addresses out of public commits.
2. Keep the local `control-plane` entry. Vantage does not scan the LAN; install the Linux agent only on workers you intend to trust.
3. Use the setup wizard or Operator Guide to install each agent and add its stable node ID and LAN URL.
4. Keep the shared agent secret in `.env` and the agent's protected env file, never in TOML, shell history, or committed docs. New installations use HMAC request signing.
5. Set `VANTAGE_AGENT_CONTROL_PLANE_CIDRS=<control-plane-ip>/32` during agent installation to apply a per-service systemd network policy, and retain host-firewall or VPN controls as defense in depth. HMAC authenticates requests but does not encrypt telemetry, prompts, or responses.
6. Start the backend and frontend with `docker compose up --build -d`.
7. Run `scripts/check-setup.ps1 -RemoteAgentUrl http://<worker-ip>:9110`, then sign in and confirm the node becomes `LIVE`.

`control-plane` is the public-safe local default. Remote workers are opt-in so a clean install does not begin in a degraded state.

## First Checks

- The header stream state should become `Live`.
- Nodes should show `LIVE`, `STALE`, or `UNREACHABLE` separately from health.
- Models should show merged placement inventory across nodes.
- Runs should show durable audit records for actions, evals, exports, and capability checks.
- Routing should show preferred node order and why a route would be accepted or rejected.
- Eval Lab should offer `Install starter suite`; install it once, queue it against an available local model, execute both cases, and set a baseline after a clean result.

## Use The Setup Wizard

Open the in-app onboarding panel and choose `Launch setup wizard`.

The wizard helps with:

- generating a high-entropy `VANTAGE_AGENT_SHARED_TOKEN` line for `.env`
- creating a worker-node TOML block for `config/vantage.bootstrap.toml`
- generating a Linux systemd-agent installation command that prompts for the secret securely
- configuring HMAC signing and the read/capability-check/eval-only v1 allowlist
- setting `VANTAGE_LOCAL_OLLAMA_BASE_URLS`
- restarting and verifying the stack

The wizard does not write files, store secrets, or change routing state. It generates snippets so the operator can review and apply them deliberately. Operator and session secrets must already exist; generate them with `scripts/rotate-control-plane-secrets.ps1` before starting Vantage.

## When Something Looks Wrong

Use the app in this order:

1. Check the attention ribbon for stale, degraded, unreachable, failed, or warning states.
2. Open the relevant node diagnostics drawer.
3. Copy the Run ID from the Runs table if the issue came from an action or eval.
4. Export runs as JSON when filing an issue so nested metadata is preserved.
