param(
    [string]$ComposeFile = "docker-compose.prod.yml",
    [string]$BootstrapConfig = "config/vantage.bootstrap.toml",
    [string]$ControlPlaneUrl = "http://127.0.0.1:8000",
    [string]$RemoteAgentUrl = "",
    [string]$AgentTokenEnv = "VANTAGE_AGENT_SHARED_TOKEN",
    [string]$AgentAuthModeEnv = "VANTAGE_AGENT_AUTH_MODE",
    [string]$AuditSigningKeyEnv = "VANTAGE_AUDIT_SIGNING_KEY",
    [string]$ExternalApiTokenEnv = "VANTAGE_EXTERNAL_API_TOKEN",
    [string]$SqlitePath = ""
)

$ErrorActionPreference = "Stop"
$failures = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

function Write-Check {
    param([string]$Name, [string]$Status, [string]$Detail = "")
    $prefix = if ($Status -eq "OK") { "[OK]" } elseif ($Status -eq "WARN") { "[WARN]" } else { "[FAIL]" }
    $line = "$prefix $Name"
    if ($Detail) {
        $line = "$line - $Detail"
    }
    Write-Host $line
}

function Add-Failure {
    param([string]$Name, [string]$Detail)
    $failures.Add("${Name}: $Detail") | Out-Null
    Write-Check $Name "FAIL" $Detail
}

function Add-Warning {
    param([string]$Name, [string]$Detail)
    $warnings.Add("${Name}: $Detail") | Out-Null
    Write-Check $Name "WARN" $Detail
}

if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Check "Docker CLI" "OK" ((docker --version) -join " ")
} else {
    Add-Failure "Docker CLI" "docker was not found on PATH"
}

try {
    docker info *> $null
    Write-Check "Docker daemon" "OK" "daemon is reachable"
} catch {
    Add-Failure "Docker daemon" "Docker is installed but the daemon is not reachable"
}

if (Test-Path $ComposeFile) {
    $originalTokenItem = Get-Item "env:$AgentTokenEnv" -ErrorAction SilentlyContinue
    $usedPlaceholderToken = $false
    try {
        if (-not $originalTokenItem) {
            Set-Item -Path "env:$AgentTokenEnv" -Value "setup-check-placeholder-token"
            $usedPlaceholderToken = $true
        }
        docker compose -f $ComposeFile config --quiet
        Write-Check "Compose config" "OK" $ComposeFile
    } catch {
        Add-Failure "Compose config" $_.Exception.Message
    } finally {
        if ($usedPlaceholderToken) {
            Remove-Item "env:$AgentTokenEnv" -ErrorAction SilentlyContinue
        }
    }
} else {
    Add-Failure "Compose config" "$ComposeFile not found"
}

$tokenItem = Get-Item "env:$AgentTokenEnv" -ErrorAction SilentlyContinue
$token = if ($tokenItem) { $tokenItem.Value } else { "" }
if ([string]::IsNullOrWhiteSpace($token)) {
    Add-Failure "Agent token" "$AgentTokenEnv is not set"
} elseif ($token.Length -lt 32 -or $token -eq "setup-check-placeholder-token") {
    Add-Warning "Agent token" "$AgentTokenEnv is set but looks weak or placeholder-like"
} else {
    Write-Check "Agent token" "OK" "$AgentTokenEnv is set"
}

$authMode = (Get-Item "env:$AgentAuthModeEnv" -ErrorAction SilentlyContinue).Value
if ([string]::IsNullOrWhiteSpace($authMode)) {
    $authMode = "bearer"
}
if ($authMode.ToLowerInvariant() -in @("bearer", "hmac", "bearer_or_hmac")) {
    Write-Check "Agent auth mode" "OK" "$AgentAuthModeEnv=$authMode"
} else {
    Add-Failure "Agent auth mode" "unsupported $AgentAuthModeEnv=$authMode"
}

$auditKey = (Get-Item "env:$AuditSigningKeyEnv" -ErrorAction SilentlyContinue).Value
if ([string]::IsNullOrWhiteSpace($auditKey)) {
    Add-Warning "Audit signing key" "$AuditSigningKeyEnv is not set; signed audit bundle export will be unavailable"
} elseif ($auditKey.Length -lt 32) {
    Add-Warning "Audit signing key" "$AuditSigningKeyEnv is set but looks short"
} else {
    Write-Check "Audit signing key" "OK" "$AuditSigningKeyEnv is set"
}

$externalToken = (Get-Item "env:$ExternalApiTokenEnv" -ErrorAction SilentlyContinue).Value
$webhookUrl = (Get-Item "env:VANTAGE_WEBHOOK_URL" -ErrorAction SilentlyContinue).Value
$slackWebhookUrl = (Get-Item "env:VANTAGE_SLACK_WEBHOOK_URL" -ErrorAction SilentlyContinue).Value
$discordWebhookUrl = (Get-Item "env:VANTAGE_DISCORD_WEBHOOK_URL" -ErrorAction SilentlyContinue).Value
$webhookAllowedHosts = (Get-Item "env:VANTAGE_WEBHOOK_ALLOWED_HOSTS" -ErrorAction SilentlyContinue).Value
if ([string]::IsNullOrWhiteSpace($externalToken)) {
    Add-Warning "External API token" "$ExternalApiTokenEnv is not set; /api/integrations/* will be open on the backend network surface"
} elseif ($externalToken.Length -lt 32) {
    Add-Warning "External API token" "$ExternalApiTokenEnv is set but looks short"
} else {
    Write-Check "External API token" "OK" "$ExternalApiTokenEnv is set"
}
if (($webhookUrl -or $slackWebhookUrl -or $discordWebhookUrl) -and [string]::IsNullOrWhiteSpace($webhookAllowedHosts)) {
    Add-Warning "Webhook allowlist" "webhook URL configured but VANTAGE_WEBHOOK_ALLOWED_HOSTS is empty"
}

if (Test-Path $BootstrapConfig) {
    Write-Check "Bootstrap config" "OK" $BootstrapConfig
} else {
    Add-Failure "Bootstrap config" "$BootstrapConfig not found"
}

$demoMode = (Get-Item "env:VANTAGE_DEMO_MODE" -ErrorAction SilentlyContinue).Value
if ($demoMode -and $demoMode.ToLowerInvariant() -in @("1", "true", "yes", "on")) {
    Add-Warning "Demo mode" "VANTAGE_DEMO_MODE is enabled; disable it for production deployments"
}

if ($SqlitePath) {
    $sqliteParent = Split-Path -Parent $SqlitePath
    if (-not $sqliteParent) {
        $sqliteParent = "."
    }
    if (Test-Path $sqliteParent) {
        Write-Check "SQLite path" "OK" "parent exists: $sqliteParent"
    } else {
        Add-Failure "SQLite path" "parent directory does not exist: $sqliteParent"
    }
} else {
    Add-Warning "SQLite path" "not provided; production Compose uses the vantage_data volume"
}

try {
    $ready = Invoke-RestMethod "$ControlPlaneUrl/api/health/ready" -TimeoutSec 5
    Write-Check "Control-plane readiness" "OK" "status=$($ready.status)"
} catch {
    Add-Warning "Control-plane readiness" "not reachable yet at $ControlPlaneUrl"
}

if ($RemoteAgentUrl) {
    if ($authMode.ToLowerInvariant() -eq "hmac") {
        Add-Warning "Remote agent" "HMAC mode configured; verify $RemoteAgentUrl/health through Vantage or a signed request client"
    } else {
        try {
            $headers = @{}
            if ($token) {
                $headers.Authorization = "Bearer $token"
            }
            $agentHealth = Invoke-RestMethod "$RemoteAgentUrl/health" -Headers $headers -TimeoutSec 5
            Write-Check "Remote agent" "OK" "status=$($agentHealth.status)"
        } catch {
            Add-Failure "Remote agent" "failed to reach $RemoteAgentUrl/health"
        }
    }
} else {
    Add-Warning "Remote agent" "not checked; pass -RemoteAgentUrl http://<remote-agent-ip>:9110"
}

if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host "Setup check failed:"
    $failures | ForEach-Object { Write-Host "- $_" }
    exit 1
}

Write-Host ""
Write-Host "Setup check completed with $($warnings.Count) warning(s)."
