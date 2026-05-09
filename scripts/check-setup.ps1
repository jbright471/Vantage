param(
    [string]$ComposeFile = "docker-compose.prod.yml",
    [string]$BootstrapConfig = "config/vantage.bootstrap.toml",
    [string]$ControlPlaneUrl = "http://127.0.0.1:8000",
    [string]$RemoteAgentUrl = "",
    [string]$AgentTokenEnv = "VANTAGE_AGENT_SHARED_TOKEN",
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

if (Test-Path $BootstrapConfig) {
    Write-Check "Bootstrap config" "OK" $BootstrapConfig
} else {
    Add-Failure "Bootstrap config" "$BootstrapConfig not found"
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
        $headers = @{}
        if ($token) {
            $headers.Authorization = "Bearer $token"
        }
        $agentHealth = Invoke-RestMethod "$RemoteAgentUrl/health" -Headers $headers -TimeoutSec 5
        Write-Check "Remote agent" "OK" "status=$($agentHealth.status)"
    } catch {
        Add-Failure "Remote agent" "failed to reach $RemoteAgentUrl/health"
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
