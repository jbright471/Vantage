param(
    [string]$ComposeFile = "docker-compose.prod.yml",
    [string]$BootstrapConfig = "config/vantage.bootstrap.toml",
    [string]$ControlPlaneUrl = "http://127.0.0.1:5173",
    [string]$RemoteAgentUrl = "",
    [string]$AgentTokenEnv = "VANTAGE_AGENT_SHARED_TOKEN",
    [string]$AgentAuthModeEnv = "VANTAGE_AGENT_AUTH_MODE",
    [string]$AgentKeyIdEnv = "VANTAGE_AGENT_KEY_ID",
    [string]$AuditSigningKeyEnv = "VANTAGE_AUDIT_SIGNING_KEY",
    [string]$ExternalApiTokenEnv = "VANTAGE_EXTERNAL_API_TOKEN",
    [string]$ControlPlaneTokenEnv = "VANTAGE_CONTROL_PLANE_TOKEN",
    [string]$SessionSigningKeyEnv = "VANTAGE_SESSION_SIGNING_KEY",
    [string]$EnvFile = ".env",
    [string]$SqlitePath = ""
)

$ErrorActionPreference = "Stop"
$failures = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]
$envFileValues = @{}

if ($EnvFile -and (Test-Path -LiteralPath $EnvFile)) {
    foreach ($line in Get-Content -LiteralPath $EnvFile) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }
        $parts = $trimmed.Split("=", 2)
        $name = $parts[0].Trim()
        $value = $parts[1].Trim()
        if ($name -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
            continue
        }
        if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $envFileValues[$name] = $value
    }
}

function Get-ConfiguredValue {
    param([string]$Name)
    $item = Get-Item "env:$Name" -ErrorAction SilentlyContinue
    if ($item) {
        return $item.Value
    }
    if ($envFileValues.ContainsKey($Name)) {
        return $envFileValues[$Name]
    }
    return ""
}

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

function Get-Sha256Hex {
    param([byte[]]$Bytes)
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($sha256.ComputeHash($Bytes))).Replace("-", "").ToLowerInvariant()
    } finally {
        $sha256.Dispose()
    }
}

function New-AgentHmacHeaders {
    param(
        [string]$Method,
        [string]$Path,
        [string]$SigningKey,
        [string]$KeyId = "",
        [byte[]]$Body = [byte[]]::new(0)
    )
    $timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds().ToString()
    $nonceBytes = [byte[]]::new(18)
    $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $random.GetBytes($nonceBytes)
    } finally {
        $random.Dispose()
    }
    $nonce = [Convert]::ToBase64String($nonceBytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
    $bodyHash = Get-Sha256Hex $Body
    $message = "$($Method.ToUpperInvariant())`n$Path`n$timestamp`n$nonce`n$bodyHash"
    $keyBytes = [System.Text.Encoding]::UTF8.GetBytes($SigningKey)
    $messageBytes = [System.Text.Encoding]::UTF8.GetBytes($message)
    $hmac = [System.Security.Cryptography.HMACSHA256]::new($keyBytes)
    try {
        $signature = ([System.BitConverter]::ToString($hmac.ComputeHash($messageBytes))).Replace("-", "").ToLowerInvariant()
    } finally {
        $hmac.Dispose()
    }
    $headers = @{
        "X-Vantage-Timestamp" = $timestamp
        "X-Vantage-Nonce" = $nonce
        "X-Vantage-Signature" = $signature
    }
    if ($KeyId) {
        $headers["X-Vantage-Key-Id"] = $KeyId
    }
    return $headers
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
    $placeholderNames = @($AgentTokenEnv, $ControlPlaneTokenEnv, $SessionSigningKeyEnv)
    $addedPlaceholders = New-Object System.Collections.Generic.List[string]
    try {
        foreach ($name in $placeholderNames) {
            if (-not (Get-Item "env:$name" -ErrorAction SilentlyContinue)) {
                Set-Item -Path "env:$name" -Value "setup-check-placeholder-token-0000000000000000"
                $addedPlaceholders.Add($name) | Out-Null
            }
        }
        docker compose -f $ComposeFile config --quiet
        Write-Check "Compose config" "OK" $ComposeFile
    } catch {
        Add-Failure "Compose config" $_.Exception.Message
    } finally {
        foreach ($name in $addedPlaceholders) {
            Remove-Item "env:$name" -ErrorAction SilentlyContinue
        }
    }
} else {
    Add-Failure "Compose config" "$ComposeFile not found"
}

$token = Get-ConfiguredValue $AgentTokenEnv
if ([string]::IsNullOrWhiteSpace($token)) {
    Add-Failure "Agent token" "$AgentTokenEnv is not set"
} elseif ($token.Length -lt 32 -or $token -like "setup-check-placeholder-token*") {
    Add-Warning "Agent token" "$AgentTokenEnv is set but looks weak or placeholder-like"
} else {
    Write-Check "Agent token" "OK" "$AgentTokenEnv is set"
}

$controlPlaneToken = Get-ConfiguredValue $ControlPlaneTokenEnv
if ([string]::IsNullOrWhiteSpace($controlPlaneToken)) {
    Add-Failure "Control-plane token" "$ControlPlaneTokenEnv is not set"
} elseif ($controlPlaneToken.Length -lt 32 -or $controlPlaneToken -like "setup-check-placeholder-token*") {
    Add-Failure "Control-plane token" "$ControlPlaneTokenEnv must be a non-placeholder value of at least 32 characters"
} else {
    Write-Check "Control-plane token" "OK" "$ControlPlaneTokenEnv is set"
}

$sessionSigningKey = Get-ConfiguredValue $SessionSigningKeyEnv
if ([string]::IsNullOrWhiteSpace($sessionSigningKey)) {
    Add-Failure "Session signing key" "$SessionSigningKeyEnv is not set"
} elseif ($sessionSigningKey.Length -lt 32 -or $sessionSigningKey -like "setup-check-placeholder-token*") {
    Add-Failure "Session signing key" "$SessionSigningKeyEnv must be a non-placeholder value of at least 32 characters"
} elseif ($sessionSigningKey -eq $controlPlaneToken) {
    Add-Failure "Session signing key" "do not reuse the operator token as the session signing key"
} else {
    Write-Check "Session signing key" "OK" "$SessionSigningKeyEnv is set independently"
}

$authMode = Get-ConfiguredValue $AgentAuthModeEnv
if ([string]::IsNullOrWhiteSpace($authMode)) {
    $authMode = "hmac"
}
if ($authMode.ToLowerInvariant() -in @("bearer", "hmac", "bearer_or_hmac")) {
    Write-Check "Agent auth mode" "OK" "$AgentAuthModeEnv=$authMode"
} else {
    Add-Failure "Agent auth mode" "unsupported $AgentAuthModeEnv=$authMode"
}

$auditKey = Get-ConfiguredValue $AuditSigningKeyEnv
if ([string]::IsNullOrWhiteSpace($auditKey)) {
    Add-Warning "Audit signing key" "$AuditSigningKeyEnv is not set; signed audit bundle export will be unavailable"
} elseif ($auditKey.Length -lt 32) {
    Add-Warning "Audit signing key" "$AuditSigningKeyEnv is set but looks short"
} else {
    Write-Check "Audit signing key" "OK" "$AuditSigningKeyEnv is set"
}

$externalToken = Get-ConfiguredValue $ExternalApiTokenEnv
$webhookUrl = Get-ConfiguredValue "VANTAGE_WEBHOOK_URL"
$slackWebhookUrl = Get-ConfiguredValue "VANTAGE_SLACK_WEBHOOK_URL"
$discordWebhookUrl = Get-ConfiguredValue "VANTAGE_DISCORD_WEBHOOK_URL"
$webhookAllowedHosts = Get-ConfiguredValue "VANTAGE_WEBHOOK_ALLOWED_HOSTS"
if ([string]::IsNullOrWhiteSpace($externalToken)) {
    Add-Warning "External API token" "$ExternalApiTokenEnv is not set; protected integration automation routes will return HTTP 503"
} elseif ($externalToken.Length -lt 32) {
    Add-Warning "External API token" "$ExternalApiTokenEnv is set but looks short"
} else {
    Write-Check "External API token" "OK" "$ExternalApiTokenEnv is set"
}
if (($webhookUrl -or $slackWebhookUrl -or $discordWebhookUrl) -and [string]::IsNullOrWhiteSpace($webhookAllowedHosts)) {
    Add-Failure "Webhook allowlist" "webhook URL configured but VANTAGE_WEBHOOK_ALLOWED_HOSTS is empty; dispatch will fail closed"
}

if (Test-Path $BootstrapConfig) {
    Write-Check "Bootstrap config" "OK" $BootstrapConfig
} else {
    Add-Failure "Bootstrap config" "$BootstrapConfig not found"
}

$demoMode = Get-ConfiguredValue "VANTAGE_DEMO_MODE"
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
    try {
        $remoteHealthUrl = "$($RemoteAgentUrl.TrimEnd('/'))/health"
        $headers = @{}
        if ($token) {
            if ($authMode.ToLowerInvariant() -in @("hmac", "bearer_or_hmac")) {
                $keyId = Get-ConfiguredValue $AgentKeyIdEnv
                $headers = New-AgentHmacHeaders -Method "GET" -Path ([Uri]$remoteHealthUrl).AbsolutePath -SigningKey $token -KeyId $keyId
            } else {
                $headers.Authorization = "Bearer $token"
            }
        }
        $agentHealth = Invoke-RestMethod $remoteHealthUrl -Headers $headers -TimeoutSec 5
        Write-Check "Remote agent" "OK" "status=$($agentHealth.status), node_id=$($agentHealth.node_id), auth=$authMode"
    } catch {
        Add-Failure "Remote agent" "failed authenticated health check at $RemoteAgentUrl"
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
