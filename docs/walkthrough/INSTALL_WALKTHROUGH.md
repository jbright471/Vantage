# Product-Ready Install Walkthrough

Use this as the script and shot list for a short install video. It is written for a public-safe demo, not a private production deployment.

## Target Runtime

- Length: 4-6 minutes.
- Audience: homelab operators, local AI builders, and infrastructure-minded developers.
- Goal: show that Vantage can be cloned, run, inspected, and pointed at real nodes without cloud dependencies.

## Recording Setup

Use demo mode so no private topology is visible:

```powershell
Copy-Item .env.example .env
(Get-Content .env) -replace '^VANTAGE_DEMO_MODE=.*', "VANTAGE_DEMO_MODE=1" | Set-Content .env
(Get-Content .env) -replace '^VANTAGE_AGENT_SHARED_TOKEN=.*', "VANTAGE_AGENT_SHARED_TOKEN=<generated-token>" | Set-Content .env
docker compose up --build -d
```

Recommended browser URL:

```text
http://127.0.0.1:5173
```

## Storyboard

| Segment | Visual | Narration |
| --- | --- | --- |
| 1. Problem | Show a terminal, Ollama endpoint, and Vantage dashboard preview. | "Local AI setups grow sideways. Vantage gives operators one place to see what is actually happening." |
| 2. Quickstart | Show `.env.example`, generated token, and `docker compose up --build -d`. | "The dev stack is Docker Compose. Secrets stay in ignored env files." |
| 3. Demo Mode | Show seeded nodes, models, runs, routing, and evals. | "Demo mode gives public-safe synthetic data for evaluation and screenshots." |
| 4. Setup Wizard | Click `Launch setup wizard`; show token, node, Ollama, verify steps. | "The wizard generates snippets instead of secretly changing your machine." |
| 5. Operator Loop | Open Nodes, Runs drawer, Routing dry-run, Eval Intelligence. | "Daily work is observe, diagnose, act deliberately, and audit every meaningful action." |
| 6. Production Path | Show `docker-compose.prod.yml`, `PORTAINER.md`, and release bundle. | "When ready, move to production Compose or Portainer with health checks and persisted SQLite." |

## Capture Checklist

- Keep the browser zoom at 100%.
- Use a 1440x1000 or 1600x1000 viewport for legibility.
- Do not show real `.env` files with live tokens.
- Do not show private IP addresses or real hostnames.
- Use `demo-control`, `demo-worker`, and placeholder URLs in all public clips.

## Voiceover Close

"Vantage is not trying to own your local AI stack. It gives you a vantage point: live telemetry, model inventory, auditable runs, routing policy, and eval intelligence, all local-first."
