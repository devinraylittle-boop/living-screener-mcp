param(
    [string]$BaseUrl = "https://living-screener-mcp.onrender.com",
    [decimal]$MaxOrderNotional = 15,
    [decimal]$MaxDailyLoss = 20,
    [decimal]$MinScore = 76,
    [decimal]$MinRelativeVolume = 0.45,
    [decimal]$MaxSpreadBps = 35,
    [string]$AllowedBrokerAlertTypes = "",
    [int]$IntervalSeconds = 60,
    [int]$MaxConsecutiveErrors = 2,
    [int]$ErrorCooldownSeconds = 300,
    [string]$MarketHours = "auto",
    [string]$AlpacaBaseUrl = "https://api.alpaca.markets",
    [string]$AlpacaDataUrl = "https://data.alpaca.markets",
    [decimal]$MaxOptionContractCost = 15,
    [decimal]$MaxOptionAccountRisk = 20,
    [switch]$EnableCryptoExecution,
    [switch]$AllowMarketOptions,
    [switch]$Live,
    [switch]$Once
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

if (-not $env:ALPACA_API_KEY_ID -or -not $env:ALPACA_API_SECRET_KEY) {
    Write-Host "Alpaca credentials are required in this PowerShell session."
    Write-Host 'Set $env:ALPACA_API_KEY_ID and $env:ALPACA_API_SECRET_KEY, then rerun this script.'
    exit 1
}

$env:SCREENER_BASE_URL = $BaseUrl
$env:STOCK_BRIDGE_BROKER = "alpaca"
$env:ALPACA_BASE_URL = $AlpacaBaseUrl
$env:ALPACA_DATA_URL = $AlpacaDataUrl
$env:STOCK_BRIDGE_MAX_ORDER_NOTIONAL = [string]$MaxOrderNotional
$env:STOCK_BRIDGE_MAX_DAILY_LOSS = [string]$MaxDailyLoss
$env:STOCK_BRIDGE_MIN_SCORE = [string]$MinScore
$env:STOCK_BRIDGE_MIN_RELATIVE_VOLUME = [string]$MinRelativeVolume
$env:STOCK_BRIDGE_MAX_SPREAD_BPS = [string]$MaxSpreadBps
$env:STOCK_BRIDGE_ALLOWED_BROKER_ALERT_TYPES = $AllowedBrokerAlertTypes
$env:STOCK_BRIDGE_INTERVAL_SECONDS = [string]$IntervalSeconds
$env:STOCK_BRIDGE_MAX_CONSECUTIVE_ERRORS = [string]$MaxConsecutiveErrors
$env:STOCK_BRIDGE_ERROR_COOLDOWN_SECONDS = [string]$ErrorCooldownSeconds
$env:STOCK_BRIDGE_MARKET_HOURS = $MarketHours
$env:MAX_OPTION_CONTRACT_COST = [string]$MaxOptionContractCost
$env:MAX_OPTION_ACCOUNT_RISK = [string]$MaxOptionAccountRisk
$env:ENABLE_CRYPTO_EXECUTION = if ($EnableCryptoExecution) { "true" } else { "false" }
$env:ALLOW_MARKET_OPTIONS = if ($AllowMarketOptions) { "true" } else { "false" }

$argsList = @("tools\stock_bridge_loop.py", "--broker", "alpaca")
if ($Live) {
    $env:STOCK_BRIDGE_LIVE = "true"
    if ($env:STOCK_BRIDGE_LIVE_AUTH -ne "ENABLE_AGENTIC_STOCK_BRIDGE") {
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
Write-Host "Starting Living Screener Alpaca stock bridge loop"
Write-Host "Repo: $repoRoot"
Write-Host "Base: $BaseUrl"
Write-Host "Broker: alpaca"
Write-Host "Alpaca API: $AlpacaBaseUrl"
Write-Host "Live: $Live"
Write-Host "Max order notional: $MaxOrderNotional"
Write-Host "Max daily loss: $MaxDailyLoss"
Write-Host "Min score: $MinScore"
Write-Host "Min relative volume: $MinRelativeVolume"
Write-Host "Max spread bps: $MaxSpreadBps"
Write-Host "Max option contract cost: $MaxOptionContractCost"
Write-Host "Max option account risk: $MaxOptionAccountRisk"
Write-Host "Crypto execution enabled: $EnableCryptoExecution"
Write-Host "Market options allowed: $AllowMarketOptions"
Write-Host "Allowed broker alerts: $AllowedBrokerAlertTypes"
Write-Host "Max consecutive errors: $MaxConsecutiveErrors"
Write-Host "Error cooldown seconds: $ErrorCooldownSeconds"
Write-Host "Market hours mode: $MarketHours"
Write-Host ""

python @argsList
