param(
    [string]$BaseUrl = "https://living-screener-mcp.onrender.com",
    [string]$ExpectedBuild = "2026.06.11-event-volatility",
    [string]$Tickers = "AMZN,SOFI,SHOP,XOM,LULU,AAPL,QQQ,IWM,MSFT,NVDA,AMD,META,AVGO,SMCI,RBLX,CVX,LLY,UNH,HOOD,TSLA",
    [int]$AccountValue = 50,
    [int]$MaxCandidates = 25,
    [int]$ReviewTopN = 8,
    [decimal]$MaxContractPrice = 1.00,
    [int]$CatalystTopN = 8,
    [int]$DefaultSleepSeconds = 300,
    [switch]$Once
)

$ErrorActionPreference = "Stop"

function Invoke-LivingScreenerJson {
    param([string]$Url)
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 75
    return $response.Content | ConvertFrom-Json
}

function Build-Query {
    param([hashtable]$Values)
    $pairs = foreach ($key in $Values.Keys) {
        "$([System.Uri]::EscapeDataString([string]$key))=$([System.Uri]::EscapeDataString([string]$Values[$key]))"
    }
    return ($pairs -join "&")
}

Write-Host "Living Screener morning pinger"
Write-Host "Base URL: $BaseUrl"
Write-Host "Expected build: $ExpectedBuild"
Write-Host "Review-only endpoint pings only. No broker action is possible from this script."
Write-Host ""

$healthUrl = "$BaseUrl/health/full?expected_build_version=$([System.Uri]::EscapeDataString($ExpectedBuild))"
$health = Invoke-LivingScreenerJson -Url $healthUrl
if ($health.result.status -ne "OK") {
    Write-Host "Health check failed:"
    $health | ConvertTo-Json -Depth 12
    exit 1
}
Write-Host "Health OK. Build: $($health.result.build_version). Tools: $($health.result.tool_count)."
Write-Host ""

do {
    $query = Build-Query @{
        tickers = $Tickers
        account_value = $AccountValue
        max_candidates = $MaxCandidates
        review_top_n = $ReviewTopN
        max_contract_price = $MaxContractPrice
        catalyst_top_n = $CatalystTopN
        format = "json"
    }
    $url = "$BaseUrl/ops/autonomous-morning-scan?$query"
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    try {
        $result = Invoke-LivingScreenerJson -Url $url
        $scan = $result.result
        Write-Host "[$timestamp] $($scan.status) | phase=$($scan.phase.phase) | next=$($scan.next_refresh_seconds)s"
        Write-Host "  $($scan.next_action)"
        $sleepSeconds = [int]($scan.next_refresh_seconds)
        if ($sleepSeconds -lt 60 -or $sleepSeconds -gt 1800) {
            $sleepSeconds = $DefaultSleepSeconds
        }
    } catch {
        Write-Host "[$timestamp] Ping failed: $($_.Exception.Message)"
        $sleepSeconds = $DefaultSleepSeconds
    }
    if (-not $Once) {
        Start-Sleep -Seconds $sleepSeconds
    }
} while (-not $Once)
