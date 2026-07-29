# Screenshot Guide

Use this guide when preparing README images, GitHub release media, or a public demo walkthrough.

## Recommended Demo Setup

Run Vantage with seeded synthetic data:

```powershell
Copy-Item .env.example .env
.\scripts\rotate-agent-token.ps1 -EnvFile .env -Apply
.\scripts\rotate-control-plane-secrets.ps1 -EnvFile .env -Apply
(Get-Content .env) -replace '^VANTAGE_DEMO_MODE=.*', "VANTAGE_DEMO_MODE=1" | Set-Content .env
Add-Content .env "VANTAGE_ENABLE_BACKGROUND_POLLING=0"
docker compose up --build -d
```

Copy the operator token to the clipboard without showing it in the recording, then sign in. This avoids exposing real node names, private IP addresses, model paths, local filesystem details, or credentials.

## Capture List

- Dashboard overview with attention ribbon, telemetry strip, and onboarding checklist.
- Nodes surface showing one healthy and one degraded demo node.
- Runs drawer showing full JSON metadata and complete Run ID.
- Models surface showing replicated model placement.
- Routing surface showing dry-run simulation and strict confirmation.
- Eval Lab with score history, visual filters, and assisted-summary controls.
- Operator Guide drawer open over live telemetry.

## Redaction Rules

- Do not publish screenshots containing real bearer tokens, `.env` values, local filesystem paths, or private IP addresses.
- Prefer `demo-control` and `demo-worker` for public captures.
- If real screenshots are unavoidable, blur base URLs, node names, model names that reveal private workflows, and any run metadata containing prompts.

## Image Naming

Store final public images under `docs/screenshots/` using lowercase descriptive names:

- `dashboard-overview.png`
- `setup-wizard.png`
- `nodes-diagnostics.png`
- `runs-drawer.png`
- `routing-simulation.png`
- `eval-intelligence.png`
- `operator-guide-drawer.png`
- `product-microsite.png`

## Current Public Captures

The repository stores public-safe captures under `docs/screenshots/`. Regenerate them from demo mode when the UI changes materially.
