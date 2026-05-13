# Walkthrough Video Plan

This folder is a lightweight scaffold for generating a product walkthrough video from public-safe demo captures.

The intended flow is Remotion-compatible, but Vantage does not require Remotion as a runtime dependency. Generate the actual video only when preparing release media and keep raw captures out of git unless they are intentionally small public artifacts.

## Release-Safe Capture Mode

Use demo mode for every public video:

```powershell
$token = python -c "import secrets; print(secrets.token_urlsafe(48))"
(Get-Content .env.example) -replace '^VANTAGE_AGENT_SHARED_TOKEN=.*', "VANTAGE_AGENT_SHARED_TOKEN=$token" | Set-Content .env
(Get-Content .env) -replace '^VANTAGE_DEMO_MODE=.*', "VANTAGE_DEMO_MODE=1" | Set-Content .env
docker compose up --build -d
```

Open `http://127.0.0.1:5173` and confirm the UI shows demo nodes rather than real hostnames, private IPs, local paths, tokens, or personal prompts.

## Storyboard

1. Product microsite: explain what Vantage is.
2. Dashboard overview: show local AI command center state.
3. Setup wizard: show first-run bootstrap snippets.
4. Operator guide drawer: show docs inside the app.

## Suggested Output

```text
dist/media/vantage-walkthrough.mp4
```

## Codex-Assisted Capture Path

1. Start Vantage in demo mode.
2. Use the in-app browser or Playwright to capture screenshots for the views listed in `manifest.json`.
3. Save public-safe PNGs under `docs/screenshots/`.
4. Review every image for tokens, private IPs, real hostnames, filesystem paths, and personal prompts.
5. Generate the video from the sanitized screenshots.

## Remotion Generation Path

1. Create a temporary Remotion project under `video/` or another ignored build folder.
2. Import `manifest.json`.
3. Render each screenshot as a timed slide with title, subtitle, and slow zoom/pan motion.
4. Export MP4 for release notes or landing-page embeds.

Keep generated videos out of git unless they are intentionally small release artifacts.

## Voiceover Arc

| Segment | Purpose |
| --- | --- |
| Product microsite | Explain that Vantage is a local-first AI command center, not a cloud control plane. |
| Dashboard overview | Show truth-over-appearance: live state, stale state, warnings, and runs are separate. |
| Nodes | Show telemetry, degraded/unreachable states, and agent-side activity. |
| Runs | Show the audit log, drawer, JSON payloads, and signed export path. |
| Routing | Show priority classes, dry-run simulation, and strict confirmations. |
| Evals | Show suites, attempts, score history, judge configuration affordances, and assisted summaries. |
| Setup wizard | Show how operators configure their own node registry and tokens deliberately. |

## Acceptance Checklist

- No real `.env` values, bearer tokens, HMAC keys, private IPs, hostnames, or local filesystem paths are visible.
- Browser zoom and viewport make table text readable in a GitHub release page.
- The video shows one full operator loop: observe, diagnose, act deliberately, and audit the result.
- The final MP4 path matches `manifest.json` or the GitHub release notes link.
