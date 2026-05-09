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
- operator documentation

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

## Release Checklist

1. Confirm tests and builds pass locally.
2. Back up any live SQLite database before updating.
3. Update `ROADMAP.md`, `OPERATIONS.md`, and relevant contract docs.
4. Run `.\scripts\build-release.ps1 -Version <version>`.
5. Inspect the generated zip and confirm no secrets or local IPs are present.
6. Verify the checksum file exists.
7. Tag the release:

```powershell
git tag v0.1.0
git push origin v0.1.0
```

8. Verify the GitHub release contains the zip and `SHA256SUMS.txt`.

Optional local scan:

```powershell
$extract = Join-Path $env:TEMP "vantage-release-check"
Expand-Archive dist/releases/vantage-<version>.zip -DestinationPath $extract -Force
rg -n "192\.168|C:\\Users|VANTAGE_AGENT_SHARED_TOKEN=\S+" $extract
Remove-Item $extract -Recurse -Force
```

The scan should not find real local addresses, local Windows paths, or populated token values. Placeholder examples are acceptable.

## Operator Install From Bundle

1. Extract the release zip on the deployment host.
2. Copy `.env.production.example` to `.env.production`.
3. Generate and set `VANTAGE_AGENT_SHARED_TOKEN`.
4. Edit `config/vantage.bootstrap.toml`.
5. Run `scripts/check-setup.ps1`.
6. Start:

```powershell
docker compose -f docker-compose.prod.yml --env-file .env.production up --build -d
```

7. Verify:

```powershell
Invoke-RestMethod http://<control-plane-host>:8000/api/health/ready
```
