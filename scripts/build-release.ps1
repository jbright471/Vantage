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
    "ARCHITECTURE.md",
    "AGENT_CONTRACT.md",
    "OPERATIONS.md",
    "OPERATOR_GUIDE.md",
    "PORTAINER.md",
    "RELEASE.md",
    "LOCAL_NODE_AGENT.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "ROADMAP.md",
    "pyproject.toml",
    "alembic.ini",
    "Dockerfile.backend.prod",
    "docker-compose.prod.yml"
)

$directories = @(
    "agent",
    "backend",
    "config",
    "deploy/agent",
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
    "scripts/check-setup.ps1"
)

foreach ($file in $files) {
    $source = Join-Path $root $file
    if (Test-Path $source) {
        $destination = Join-Path $staging $file
        New-Item -ItemType Directory -Force (Split-Path -Parent $destination) | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination
    }
}

foreach ($item in $directories) {
    $source = Join-Path $root $item
    if (Test-Path $source) {
        $destination = Join-Path $staging $item
        New-Item -ItemType Directory -Force (Split-Path -Parent $destination) | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination -Recurse
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
2. Generate and set `VANTAGE_AGENT_SHARED_TOKEN`.
3. Edit `config/vantage.bootstrap.toml` for your node names and agent URLs.
4. Run `scripts/check-setup.ps1`.
5. Start with `docker compose -f docker-compose.prod.yml --env-file .env.production up --build -d`.
"@ | Set-Content -Path (Join-Path $staging "RELEASE_NOTES.md") -Encoding utf8

if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $zipPath -Force

$hash = Get-FileHash -Algorithm SHA256 $zipPath
"$($hash.Hash.ToLowerInvariant())  $(Split-Path -Leaf $zipPath)" | Set-Content -Path $checksumsPath -Encoding ascii

Write-Host "Release bundle: $zipPath"
Write-Host "Checksums: $checksumsPath"
