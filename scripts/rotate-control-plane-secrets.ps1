param(
    [string]$EnvFile = ".env",
    [switch]$Apply,
    [switch]$ShowSecrets
)

$ErrorActionPreference = "Stop"

$controlPlaneToken = python -c "import secrets; print(secrets.token_urlsafe(48))"
$sessionSigningKey = python -c "import secrets; print(secrets.token_urlsafe(48))"

function Set-EnvValue {
    param([string[]]$Content, [string]$Name, [string]$Value)
    if ($Content -match "^$Name=") {
        return @($Content -replace "^$Name=.*", "$Name=$Value")
    }
    return @($Content + "$Name=$Value")
}

if ($Apply) {
    $content = if (Test-Path $EnvFile) { @(Get-Content $EnvFile) } else { @() }
    $content = Set-EnvValue -Content $content -Name "VANTAGE_CONTROL_PLANE_TOKEN" -Value $controlPlaneToken
    $content = Set-EnvValue -Content $content -Name "VANTAGE_SESSION_SIGNING_KEY" -Value $sessionSigningKey
    $content | Set-Content $EnvFile
    Write-Host "Updated $EnvFile with independent control-plane and session secrets."
} else {
    Write-Host "Generated independent control-plane and session secrets (dry run; values were not written)."
    Write-Host "Re-run with -Apply to update $EnvFile."
}

if ($ShowSecrets) {
    Write-Host "VANTAGE_CONTROL_PLANE_TOKEN=$controlPlaneToken"
    Write-Host "VANTAGE_SESSION_SIGNING_KEY=$sessionSigningKey"
} else {
    Write-Host "Secret values were not printed. Use -ShowSecrets only when your terminal output is private."
}

Write-Host "Restart Vantage after applying the new values; existing browser sessions will be invalidated."
