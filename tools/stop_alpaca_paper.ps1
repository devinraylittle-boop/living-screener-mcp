$ErrorActionPreference = "Stop"

$processes = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "python.exe" -and $_.CommandLine -like "*stock_bridge_loop.py*" -and $_.CommandLine -like "*--broker alpaca*"
}

foreach ($process in $processes) {
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
}

[pscustomobject]@{
    StoppedCount = @($processes).Count
    StoppedProcessIds = @($processes | ForEach-Object { $_.ProcessId })
}
