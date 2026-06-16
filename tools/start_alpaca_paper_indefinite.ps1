param(
    [int]$IntervalSeconds = 60,
    [decimal]$MaxOrderNotional = 250,
    [decimal]$MaxDailyLoss = 5000,
    [decimal]$MinScore = 60,
    [decimal]$MinRelativeVolume = 0.15,
    [decimal]$MaxSpreadBps = 100,
    [int]$MaxOpenPositions = 10,
    [int]$MaxTradesPerDay = 50,
    [decimal]$StopLossPct = 0.01,
    [decimal]$TakeProfitPct = 0.015,
    [string]$PythonPath = "C:\Users\devin\AppData\Local\Python\pythoncore-3.14-64\python.exe"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$envPath = Join-Path $repoRoot ".env.local"
& (Join-Path $scriptDir "load_local_env.ps1") -Path $envPath

if (-not $env:ALPACA_API_KEY_ID -or -not $env:ALPACA_API_SECRET_KEY) {
    throw "Alpaca paper credentials missing. Create .env.local first."
}

$env:ALPACA_BASE_URL = if ($env:ALPACA_BASE_URL) { $env:ALPACA_BASE_URL } else { "https://paper-api.alpaca.markets/v2" }
$env:ALPACA_DATA_URL = if ($env:ALPACA_DATA_URL) { $env:ALPACA_DATA_URL } else { "https://data.alpaca.markets" }
$env:AUTONOMY_STAGE = "stage_2_paper_trading_automation"
$env:STOCK_BRIDGE_BROKER = "alpaca"
$env:STOCK_BRIDGE_LIVE = "true"

$out = Join-Path $repoRoot "data\alpaca_paper_indefinite.out.log"
$err = Join-Path $repoRoot "data\alpaca_paper_indefinite.err.log"
New-Item -ItemType Directory -Force -Path (Join-Path $repoRoot "data") | Out-Null

$existing = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "python.exe" -and $_.CommandLine -like "*stock_bridge_loop.py*" -and $_.CommandLine -like "*--broker alpaca*"
}
if ($existing) {
    [pscustomobject]@{
        Status = "already_running"
        ProcessId = ($existing | Select-Object -First 1).ProcessId
        OutLog = $out
        ErrLog = $err
    }
    return
}

$argsList = @(
    "tools\stock_bridge_loop.py",
    "--broker", "alpaca",
    "--live",
    "--interval-seconds", [string]$IntervalSeconds,
    "--min-score", [string]$MinScore,
    "--min-relative-volume", [string]$MinRelativeVolume,
    "--max-spread-bps", [string]$MaxSpreadBps,
    "--max-order-notional", [string]$MaxOrderNotional,
    "--max-open-positions", [string]$MaxOpenPositions,
    "--max-trades-per-day", [string]$MaxTradesPerDay,
    "--max-daily-loss", [string]$MaxDailyLoss,
    "--stop-loss-pct", [string]$StopLossPct,
    "--take-profit-pct", [string]$TakeProfitPct
)

$process = Start-Process -FilePath $PythonPath -ArgumentList $argsList -WorkingDirectory $repoRoot -RedirectStandardOutput $out -RedirectStandardError $err -WindowStyle Hidden -PassThru

[pscustomobject]@{
    Status = "started"
    ProcessId = $process.Id
    OutLog = $out
    ErrLog = $err
}
