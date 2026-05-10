# Release Packaging

Vantage releases are built as GitHub release bundles plus source-controlled Docker Compose assets.

## Release Artifacts

The release workflow publishes:

- `vantage-<version>.zip`
- `SHA256SUMS.txt`

The zip bundle includes:

- production Compose file
- production backend and frontend Dockerfiles
- backend, frontend, agent, and migration source needed for image builds
- generic bootstrap config sample
- remote-agent installer assets
- setup-check script
- token-rotation helper script
- audit-bundle verification helper script
- security hardening notes under `docs/security/`
- integration examples under `docs/integrations/`
- operator documentation
- open-source metadata such as license, changelog, support guide, and issue templates
- product microsite, screenshot assets, and install walkthrough script
- Remotion-ready walkthrough video scaffold and manifest

The bundle intentionally excludes:

- `.env`
- `.env.production`
- `vantage.sqlite3`
- node modules
- frontend build output
- local logs
- machine-specific bootstrap config values

The release script replaces the live bootstrap config with `config/vantage.bootstrap.example.toml` inside the bundle so private node URLs do not leak into release artifacts.

## Build Locally

```powershell
.\scripts\build-release.ps1 -Version v0.1.0
```

Output:

```text
dist/releases/vantage-v0.1.0.zip
dist/releases/SHA256SUMS.txt
```

## GitHub Release Workflow

The GitHub Actions release workflow runs on tags matching:

```text
v*
```

It verifies:

- backend tests
- frontend tests
- frontend production build
- production Compose config
- release bundle creation

Then it uploads the zip bundle and checksum file to the GitHub release.

## Hosted Documentation Workflow

The GitHub Pages workflow publishes public-safe product assets from `docs/product/`, `docs/screenshots/`, `README.md`, and `ROADMAP.md` when documentation or product assets change on the default branch. Use it for a lightweight landing page or hosted documentation surface without changing the Vantage runtime.

## Release Checklist

1. Confirm tests and builds pass locally.
2. Back up any live SQLite database before updating.
3. Update `ROADMAP.md`, `OPERATIONS.md`, `SECURITY.md`, and relevant contract docs.
4. Update `CHANGELOG.md` and draft release notes from `RELEASE_ANNOUNCEMENT_TEMPLATE.md`.
5. Run demo mode and capture any screenshots using `SCREENSHOTS.md`.
6. Run `.\scripts\build-release.ps1 -Version <version>`.
7. Inspect the generated zip and confirm no secrets or local IPs are present.
8. Run through `docs/security/RELEASE_SECURITY_CHECKLIST.md`.
9. Verify `scripts/verify-audit-bundle.py` is included if signed bundle exports are part of the release promise.
10. Verify the checksum file exists.
11. Tag the release:

```powershell
git tag v0.1.0
git push origin v0.1.0
```

12. Verify the GitHub release contains the zip and `SHA256SUMS.txt`.

Optional local scan:

```powershell
$extract = Join-Path $env:TEMP "vantage-release-check"
Expand-Archive dist/releases/vantage-<version>.zip -DestinationPath $extract -Force
rg -n "192\.168|[A-Za-z]:\\\\Users|VANTAGE_AGENT_SHARED_TOKEN=[A-Za-z0-9_-]{20,}" $extract
Remove-Item $extract -Recurse -Force
```

The scan should not find real local addresses, local Windows paths, or populated token values. Placeholder examples are acceptable.

## Operator Install From Bundle

1. Extract the release zip on the deployment host.
2. Copy `.env.production.example` to `.env.production`.
3. Generate and set `VANTAGE_AGENT_SHARED_TOKEN`.
4. Optionally generate and set `VANTAGE_AUDIT_SIGNING_KEY` for signed audit bundles.
5. Optionally generate and set `VANTAGE_EXTERNAL_API_TOKEN` before connecting n8n or scripts.
6. Edit `config/vantage.bootstrap.toml`.
7. Run `scripts/check-setup.ps1`.
8. Start:

```powershell
docker compose -f docker-compose.prod.yml --env-file .env.production up --build -d
```

9. Verify:

```powershell
Invoke-RestMethod http://<control-plane-host>:8000/api/health/ready
```

## Public Demo From Source

For a public-safe demo instance:

```powershell
Copy-Item .env.example .env
Add-Content .env "VANTAGE_DEMO_MODE=1"
Add-Content .env "VANTAGE_ENABLE_BACKGROUND_POLLING=0"
$token = python -c "import secrets; print(secrets.token_urlsafe(48))"
(Get-Content .env) -replace '^VANTAGE_AGENT_SHARED_TOKEN=.*', "VANTAGE_AGENT_SHARED_TOKEN=$token" | Set-Content .env
docker compose up --build -d
```

This keeps screenshots and walkthroughs on synthetic state instead of real homelab telemetry.
