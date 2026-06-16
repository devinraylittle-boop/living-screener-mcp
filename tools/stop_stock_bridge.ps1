$ErrorActionPreference = "Stop"

$processes = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "python.exe" -and
    $_.CommandLine -like "*stock_bridge_loop.py*" -and
    $_.CommandLine -notlike "*--broker alpaca*"
}

$stopped = @()
foreach ($process in $processes) {
    Stop-Process -Id $process.ProcessId -Force
    $stopped += $process.ProcessId
}

[pscustomobject]@{
    StoppedCount = $stopped.Count
    StoppedProcessIds = $stopped
}

