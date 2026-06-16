$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$statePath = Join-Path $repoRoot "data\stock_bridge_state.json"
$logPath = Join-Path $repoRoot "data\stock_bridge_loop.jsonl"
$errPath = Join-Path $repoRoot "data\alpaca_paper_indefinite.err.log"

$processes = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "python.exe" -and $_.CommandLine -like "*stock_bridge_loop.py*" -and $_.CommandLine -like "*--broker alpaca*"
}

$state = $null
if (Test-Path -LiteralPath $statePath) {
    $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
}

$recentEvents = @()
if (Test-Path -LiteralPath $logPath) {
    $recentEvents = Get-Content -LiteralPath $logPath -Tail 12
}

$recentErrors = @()
if (Test-Path -LiteralPath $errPath) {
    $recentErrors = Get-Content -LiteralPath $errPath -Tail 12
}

[pscustomobject]@{
    Running = [bool]$processes
    ProcessIds = @($processes | ForEach-Object { $_.ProcessId })
    State = $state
    RecentEvents = $recentEvents
    RecentErrors = $recentErrors
}
