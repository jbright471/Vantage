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
- agent and control-plane secret-rotation helper scripts
- audit-bundle verification helper script
- security audit and machine-readable findings
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

## Security Workflow

The SHA-pinned `.github/workflows/security.yml` workflow runs on pull requests, default-branch pushes, a weekly schedule, and manual dispatch. It covers full-history secret scanning, dependency review, npm and Python audits, OSV-Scanner, Semgrep, CodeQL, Trivy filesystem/image scans, and CycloneDX SBOM generation.

Do not publish a release unless the security workflow is green for the exact release commit. Download and retain the backend and frontend SBOM artifacts with the release evidence.

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
9. Verify the GitHub security workflow is green for the exact commit and retain its SBOM artifacts.
10. Verify `scripts/verify-audit-bundle.py` is included if signed bundle exports are part of the release promise.
11. Complete the unchecked external-host items in `docs/architecture/V1_MULTI_NODE_ACCEPTANCE.md`: a clean external-user Linux install, the starter eval suite, and source-scoped denial from an unrelated LAN address. The Bastet upgrade and restart-recovery paths are verified.
12. Verify the checksum file exists.
13. Tag the release:

```powershell
git tag v0.1.0
git push origin v0.1.0
```

14. Verify the GitHub release contains the zip and `SHA256SUMS.txt`.

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
3. Run `scripts/rotate-agent-token.ps1 -EnvFile .env.production -Apply`.
4. Run `scripts/rotate-control-plane-secrets.ps1 -EnvFile .env.production -Apply -IncludeAuditSigningKey`.
5. Preserve the generated `VANTAGE_AUDIT_SIGNING_KEY` so previously exported bundles remain verifiable.
6. Optionally generate and set `VANTAGE_EXTERNAL_API_TOKEN` before connecting n8n or scripts.
7. Edit `config/vantage.bootstrap.toml`.
8. Run `scripts/check-setup.ps1 -EnvFile .env.production`.
9. Start:

```powershell
docker compose -f docker-compose.prod.yml --env-file .env.production up --build -d
```

10. Verify through the published frontend:

```powershell
Invoke-RestMethod http://<control-plane-host>:5173/api/health/ready
```

## Public Demo From Source

For a public-safe demo instance:

```powershell
Copy-Item .env.example .env
Add-Content .env "VANTAGE_DEMO_MODE=1"
Add-Content .env "VANTAGE_ENABLE_BACKGROUND_POLLING=0"
.\scripts\rotate-agent-token.ps1 -EnvFile .env -Apply
.\scripts\rotate-control-plane-secrets.ps1 -EnvFile .env -Apply -IncludeAuditSigningKey
docker compose up --build -d
```

This keeps screenshots and walkthroughs on synthetic state instead of real homelab telemetry.
