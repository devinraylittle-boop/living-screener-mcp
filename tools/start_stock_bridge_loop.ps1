param(
    [string]$BaseUrl = "https://living-screener-mcp.onrender.com",
    [string]$AccountNumber = "628006199",
    [decimal]$MaxOrderNotional = 10,
    [decimal]$MaxDailyLoss = 20,
    [decimal]$MinScore = 76,
    [decimal]$MinRelativeVolume = 0.45,
    [decimal]$MaxSpreadBps = 35,
    [string]$AllowedBrokerAlertTypes = "EQUITY_SUITABILITY",
    [int]$IntervalSeconds = 60,
    [switch]$Live,
    [switch]$Once
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

$env:SCREENER_BASE_URL = $BaseUrl
$env:ROBINHOOD_ACCOUNT_NUMBER = $AccountNumber
$env:STOCK_BRIDGE_MAX_ORDER_NOTIONAL = [string]$MaxOrderNotional
$env:STOCK_BRIDGE_MAX_DAILY_LOSS = [string]$MaxDailyLoss
$env:STOCK_BRIDGE_MIN_SCORE = [string]$MinScore
$env:STOCK_BRIDGE_MIN_RELATIVE_VOLUME = [string]$MinRelativeVolume
$env:STOCK_BRIDGE_MAX_SPREAD_BPS = [string]$MaxSpreadBps
$env:STOCK_BRIDGE_ALLOWED_BROKER_ALERT_TYPES = $AllowedBrokerAlertTypes
$env:STOCK_BRIDGE_INTERVAL_SECONDS = [string]$IntervalSeconds

$argsList = @("tools\stock_bridge_loop.py")
if ($Live) {
    $env:STOCK_BRIDGE_LIVE = "true"
    if (-not $env:STOCK_BRIDGE_LIVE_AUTH) {
        Write-Host "Live mode requires standing authorization."
        Write-Host "Run this first in the same PowerShell session:"
        Write-Host '$env:STOCK_BRIDGE_LIVE_AUTH="ENABLE_AGENTIC_STOCK_BRIDGE"'
        exit 1
    }
    $argsList += "--live"
} else {
    $env:STOCK_BRIDGE_LIVE = "false"
}
if ($Once) {
    $argsList += "--once"
}

Set-Location $repoRoot
Write-Host "Starting Living Screener stock bridge loop"
Write-Host "Repo: $repoRoot"
Write-Host "Base: $BaseUrl"
Write-Host "Account: $AccountNumber"
Write-Host "Live: $Live"
Write-Host "Max order notional: $MaxOrderNotional"
Write-Host "Max daily loss: $MaxDailyLoss"
Write-Host "Min score: $MinScore"
Write-Host "Min relative volume: $MinRelativeVolume"
Write-Host "Max spread bps: $MaxSpreadBps"
Write-Host "Allowed broker alerts: $AllowedBrokerAlertTypes"
Write-Host ""

python @argsList
