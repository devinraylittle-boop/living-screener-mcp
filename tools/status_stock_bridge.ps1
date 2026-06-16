$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$statePath = Join-Path $repoRoot "data\stock_bridge_state.json"
$logPath = Join-Path $repoRoot "data\stock_bridge_loop.jsonl"

$processes = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "python.exe" -and
    $_.CommandLine -like "*stock_bridge_loop.py*" -and
    $_.CommandLine -notlike "*--broker alpaca*"
}

$state = $null
if (Test-Path -LiteralPath $statePath) {
    try {
        $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    } catch {
        $state = "UNREADABLE_STATE_JSON"
    }
}

$recent = @()
if (Test-Path -LiteralPath $logPath) {
    $recent = Get-Content -LiteralPath $logPath -Tail 8
}

[pscustomobject]@{
    Running = [bool]$processes
    ProcessIds = @($processes | ForEach-Object { $_.ProcessId })
    State = $state
    RecentEvents = $recent
}

