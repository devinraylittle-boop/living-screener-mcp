param(
    [string]$BaseUrl = "https://living-screener-mcp.onrender.com",
    [string]$ExpectedBuild = "2026.06.10-manual-snapshot-form",
    [int]$AccountValue = 50,
    [string]$Tickers = "AMZN,SOFI,SHOP,XOM,LULU,AAPL,QQQ,IWM,MSFT,NVDA,AMD,META,AVGO,SMCI,RBLX,CVX,LLY,UNH,HOOD,TSLA"
)

$ErrorActionPreference = "Stop"

$validator = Join-Path $PSScriptRoot "validate_live.ps1"
& $validator -BaseUrl $BaseUrl -ExpectedBuild $ExpectedBuild -AccountValue $AccountValue

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Start aborted because live validation did not pass."
    exit $LASTEXITCODE
}

$encodedTickers = [System.Uri]::EscapeDataString($Tickers)
$urls = @(
    "$BaseUrl/",
    "$BaseUrl/ops/go-live-rehearsal?account_value=$AccountValue&format=html",
    "$BaseUrl/ops/day-monitor?tickers=$encodedTickers&account_value=$AccountValue&max_candidates=25&review_top_n=8&max_contract_price=1.00&format=html",
    "$BaseUrl/ops/day-alerts?limit=50&format=html",
    "$BaseUrl/trade/manual-form?format=html",
    "$BaseUrl/paper/options/summary?format=html",
    "$BaseUrl/journal/checkpoint?limit=500&format=html"
)

Write-Host ""
Write-Host "Opening tomorrow's control pages."
$urls | ForEach-Object {
    Write-Host $_
    Start-Process $_
}

Write-Host ""
Write-Host "START_TOMORROW_READY"
