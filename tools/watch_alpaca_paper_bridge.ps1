param(
    [int]$CheckSeconds = 60,
    [int]$MaxRestartsPerHour = 12
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$watchdogLog = Join-Path $repoRoot "data\watchdog_alpaca_paper.log"
New-Item -ItemType Directory -Force -Path (Join-Path $repoRoot "data") | Out-Null

function Write-WatchdogLog {
    param([string]$Message)
    $line = "$(Get-Date -Format o) $Message"
    Add-Content -LiteralPath $watchdogLog -Value $line
}

Write-WatchdogLog "watchdog_start check_seconds=$CheckSeconds max_restarts_per_hour=$MaxRestartsPerHour"

$restartTimes = New-Object System.Collections.Generic.List[datetime]

while ($true) {
    try {
        $processes = Get-CimInstance Win32_Process | Where-Object {
            $_.Name -eq "python.exe" -and $_.CommandLine -like "*stock_bridge_loop.py*" -and $_.CommandLine -like "*--broker alpaca*"
        }

        if (-not $processes) {
            $cutoff = (Get-Date).AddHours(-1)
            $restartTimes = [System.Collections.Generic.List[datetime]]($restartTimes | Where-Object { $_ -gt $cutoff })
            if ($restartTimes.Count -ge $MaxRestartsPerHour) {
                Write-WatchdogLog "restart_suppressed max_restarts_per_hour_reached count=$($restartTimes.Count)"
            } else {
                Write-WatchdogLog "bridge_missing restarting"
                $result = & (Join-Path $scriptDir "start_alpaca_paper_indefinite.ps1")
                $restartTimes.Add((Get-Date))
                Write-WatchdogLog "restart_result $($result | ConvertTo-Json -Compress)"
            }
        } else {
            $ids = @($processes | ForEach-Object { $_.ProcessId }) -join ","
            Write-WatchdogLog "bridge_ok process_ids=$ids"
        }
    } catch {
        Write-WatchdogLog "watchdog_error $($_.Exception.Message)"
    }

    Start-Sleep -Seconds $CheckSeconds
}
