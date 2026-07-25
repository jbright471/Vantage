param(
    [string]$Version = "",
    [string]$OutputDir = "dist/releases"
)

$ErrorActionPreference = "Stop"

if (-not $Version) {
    $Version = if ($env:GITHUB_REF_NAME) { $env:GITHUB_REF_NAME } else { "dev-" + (Get-Date -Format "yyyyMMdd-HHmmss") }
}

$safeVersion = $Version -replace "[^A-Za-z0-9._-]", "-"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$releaseRoot = Join-Path $root $OutputDir
$staging = Join-Path $releaseRoot "vantage-$safeVersion"
$zipPath = Join-Path $releaseRoot "vantage-$safeVersion.zip"
$checksumsPath = Join-Path $releaseRoot "SHA256SUMS.txt"

if (Test-Path $staging) {
    Remove-Item -LiteralPath $staging -Recurse -Force
}
New-Item -ItemType Directory -Force $staging | Out-Null

$files = @(
    ".env.example",
    ".env.production.example",
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "ARCHITECTURE.md",
    "AGENT_CONTRACT.md",
    "GETTING_STARTED.md",
    "OPERATIONS.md",
    "OPERATOR_GUIDE.md",
    "PORTAINER.md",
    "RELEASE.md",
    "RELEASE_ANNOUNCEMENT_TEMPLATE.md",
    "LOCAL_NODE_AGENT.md",
    "SECURITY.md",
    "SECURITY_AUDIT.md",
    ".security/findings.json",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SUPPORT.md",
    "SCREENSHOTS.md",
    "ROADMAP.md",
    "pyproject.toml",
    "alembic.ini",
    "Dockerfile.backend.prod",
    "docker-compose.prod.yml"
)

$directories = @(
    "agent",
    ".github",
    "backend",
    "config",
    "deploy/agent",
    "docs",
    "frontend/src",
    "frontend/public",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/Dockerfile.prod",
    "frontend/nginx.conf",
    "frontend/index.html",
    "frontend/tsconfig.json",
    "frontend/tsconfig.app.json",
    "frontend/tsconfig.node.json",
    "frontend/vite.config.ts",
    "migrations",
    "scripts/build-release.ps1",
    "scripts/check-setup.ps1",
    "scripts/rotate-agent-token.ps1",
    "scripts/rotate-control-plane-secrets.ps1",
    "scripts/verify-audit-bundle.py"
)

foreach ($file in $files) {
    $source = Join-Path $root $file
    if (Test-Path $source) {
        $destination = Join-Path $staging $file
        New-Item -ItemType Directory -Force (Split-Path -Parent $destination) | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination
    }
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git is required to build a release bundle from tracked source files"
}

$trackedDirectoryFiles = @(
    foreach ($item in $directories) {
        git -C $root ls-files -- $item
        if ($LASTEXITCODE -ne 0) {
            throw "git ls-files failed while collecting release path: $item"
        }
    }
)

foreach ($relativePath in ($trackedDirectoryFiles | Sort-Object -Unique)) {
    $source = Join-Path $root $relativePath
    if (Test-Path -LiteralPath $source -PathType Leaf) {
        $destination = Join-Path $staging $relativePath
        New-Item -ItemType Directory -Force (Split-Path -Parent $destination) | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination
    }
}

$liveConfig = Join-Path $staging "config/vantage.bootstrap.toml"
Copy-Item -LiteralPath (Join-Path $root "config/vantage.bootstrap.example.toml") -Destination $liveConfig -Force

@"
# Vantage Release Bundle

Version: $Version

This bundle is safe to share. It includes production Compose assets, source code required for image builds, generic sample config, remote-agent installer assets, migrations, and operator documentation.

Before deployment:

1. Copy `.env.production.example` to `.env.production`.
2. Run `scripts/rotate-agent-token.ps1 -EnvFile .env.production -Apply`.
3. Run `scripts/rotate-control-plane-secrets.ps1 -EnvFile .env.production -Apply`.
4. Optionally generate and set `VANTAGE_AUDIT_SIGNING_KEY` for signed audit bundles.
5. Optionally generate and set `VANTAGE_EXTERNAL_API_TOKEN` before connecting n8n or scripts.
6. Edit `config/vantage.bootstrap.toml` for your node names and agent URLs.
7. Run `scripts/check-setup.ps1 -EnvFile .env.production`.
8. Start with `docker compose -f docker-compose.prod.yml --env-file .env.production up --build -d`.
"@ | Set-Content -Path (Join-Path $staging "RELEASE_NOTES.md") -Encoding utf8

if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $zipPath -Force

$hash = Get-FileHash -Algorithm SHA256 $zipPath
"$($hash.Hash.ToLowerInvariant())  $(Split-Path -Leaf $zipPath)" | Set-Content -Path $checksumsPath -Encoding ascii

Write-Host "Release bundle: $zipPath"
Write-Host "Checksums: $checksumsPath"
