param(
    [string]$EnvFile = ".env",
    [switch]$Apply,
    [switch]$IncludeAgentSharedToken,
    [switch]$AgentSharedTokenOnly,
    [switch]$IncludeAuditSigningKey,
    [switch]$ShowSecrets
)

$ErrorActionPreference = "Stop"

$controlPlaneToken = python -c "import secrets; print(secrets.token_urlsafe(48))"
$sessionSigningKey = python -c "import secrets; print(secrets.token_urlsafe(48))"
$agentSharedToken = if ($IncludeAgentSharedToken -or $AgentSharedTokenOnly) {
    python -c "import secrets; print(secrets.token_urlsafe(48))"
} else {
    $null
}
$auditSigningKey = if ($IncludeAuditSigningKey) {
    python -c "import secrets; print(secrets.token_urlsafe(48))"
} else {
    $null
}

function Set-EnvValue {
    param([string[]]$Content, [string]$Name, [string]$Value)
    if ($Content -match "^$Name=") {
        return @($Content -replace "^$Name=.*", "$Name=$Value")
    }
    return @($Content + "$Name=$Value")
}

if ($Apply) {
    $content = if (Test-Path $EnvFile) { @(Get-Content $EnvFile) } else { @() }
    if (-not $AgentSharedTokenOnly) {
        $content = Set-EnvValue -Content $content -Name "VANTAGE_CONTROL_PLANE_TOKEN" -Value $controlPlaneToken
        $content = Set-EnvValue -Content $content -Name "VANTAGE_SESSION_SIGNING_KEY" -Value $sessionSigningKey
    }
    if ($IncludeAgentSharedToken -or $AgentSharedTokenOnly) {
        $content = Set-EnvValue -Content $content -Name "VANTAGE_AGENT_SHARED_TOKEN" -Value $agentSharedToken
    }
    if ($IncludeAuditSigningKey) {
        $content = Set-EnvValue -Content $content -Name "VANTAGE_AUDIT_SIGNING_KEY" -Value $auditSigningKey
    }
    $content | Set-Content $EnvFile
    $updatedSecrets = if ($AgentSharedTokenOnly) { @() } else { @("control-plane", "session") }
    if ($IncludeAgentSharedToken -or $AgentSharedTokenOnly) { $updatedSecrets += "agent-shared" }
    if ($IncludeAuditSigningKey) { $updatedSecrets += "audit-signing" }
    $updatedSecrets = ($updatedSecrets -join ", ") + " secrets"
    Write-Host "Updated $EnvFile with $updatedSecrets."
} else {
    $generatedSecrets = if ($AgentSharedTokenOnly) { @() } else { @("control-plane", "session") }
    if ($IncludeAgentSharedToken -or $AgentSharedTokenOnly) { $generatedSecrets += "agent-shared" }
    if ($IncludeAuditSigningKey) { $generatedSecrets += "audit-signing" }
    $generatedSecrets = ($generatedSecrets -join ", ") + " secrets"
    Write-Host "Generated $generatedSecrets (dry run; values were not written)."
    Write-Host "Re-run with -Apply to update $EnvFile."
}

if ($ShowSecrets) {
    if (-not $AgentSharedTokenOnly) {
        Write-Host "VANTAGE_CONTROL_PLANE_TOKEN=$controlPlaneToken"
        Write-Host "VANTAGE_SESSION_SIGNING_KEY=$sessionSigningKey"
    }
    if ($IncludeAgentSharedToken -or $AgentSharedTokenOnly) {
        Write-Host "VANTAGE_AGENT_SHARED_TOKEN=$agentSharedToken"
    }
    if ($IncludeAuditSigningKey) {
        Write-Host "VANTAGE_AUDIT_SIGNING_KEY=$auditSigningKey"
    }
} else {
    Write-Host "Secret values were not printed. Use -ShowSecrets only when your terminal output is private."
}

if ($AgentSharedTokenOnly) {
    Write-Host "Restart the Vantage backend and update each remote agent after applying the new value."
} else {
    Write-Host "Restart Vantage after applying the new values; existing browser sessions will be invalidated."
}
