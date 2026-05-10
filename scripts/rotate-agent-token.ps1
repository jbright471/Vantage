param(
    [string]$EnvFile = ".env.production",
    [string]$TokenName = "VANTAGE_AGENT_SHARED_TOKEN",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

$token = python -c "import secrets; print(secrets.token_urlsafe(48))"

Write-Host "Generated new Vantage agent token."
Write-Host ""
Write-Host "$TokenName=$token"
Write-Host ""

if ($Apply) {
    if (Test-Path $EnvFile) {
        $content = Get-Content $EnvFile
        if ($content -match "^$TokenName=") {
            $content = $content -replace "^$TokenName=.*", "$TokenName=$token"
        } else {
            $content += "$TokenName=$token"
        }
        $content | Set-Content $EnvFile
    } else {
        "$TokenName=$token" | Set-Content $EnvFile
    }
    Write-Host "Updated $EnvFile."
} else {
    Write-Host "Dry run only. Re-run with -Apply to update $EnvFile."
}

Write-Host ""
Write-Host "Rotation workflow:"
Write-Host "1. Put the new token into the control-plane env file or secret store."
Write-Host "2. Put the same token into each remote agent env file."
Write-Host "3. Restart the control-plane backend."
Write-Host "4. Restart each vantage-agent service."
Write-Host "5. Verify /api/health/ready and each remote /health endpoint."
Write-Host "6. Delete any shell history, tickets, or notes that captured the old live token."
