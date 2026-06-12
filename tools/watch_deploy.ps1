param(
    [string]$BaseUrl = "https://living-screener-mcp.onrender.com",
    [string]$ExpectedBuild = "2026.06.10-manual-snapshot-form",
    [int]$AccountValue = 50,
    [int]$PollSeconds = 30,
    [int]$MaxMinutes = 20
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Net.Http

$client = [System.Net.Http.HttpClient]::new()
$client.Timeout = [TimeSpan]::FromSeconds(20)
$deadline = (Get-Date).AddMinutes($MaxMinutes)

Write-Host "Watching Render for build $ExpectedBuild"
Write-Host "Base URL: $BaseUrl"
Write-Host "Polling every $PollSeconds seconds for up to $MaxMinutes minutes."
Write-Host ""

while ((Get-Date) -lt $deadline) {
    $now = Get-Date -Format "HH:mm:ss"
    try {
        $response = $client.GetAsync("$BaseUrl/version").GetAwaiter().GetResult()
        $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        if ($body.Contains($ExpectedBuild)) {
            Write-Host "[$now] Expected build is live."
            Write-Host ""
            $validator = Join-Path $PSScriptRoot "validate_live.ps1"
            & $validator -BaseUrl $BaseUrl -ExpectedBuild $ExpectedBuild -AccountValue $AccountValue
            exit $LASTEXITCODE
        }

        $current = "unknown"
        if ($body -match '"build_version"\s*:\s*"([^"]+)"') {
            $current = $Matches[1]
        }
        Write-Host "[$now] Still waiting. Current build: $current"
    }
    catch {
        Write-Host "[$now] Waiting. Version check failed: $($_.Exception.Message)"
    }

    Start-Sleep -Seconds $PollSeconds
}

Write-Host ""
Write-Host "DEPLOY_WATCH_TIMEOUT"
Write-Host "Expected build did not appear before timeout: $ExpectedBuild"
exit 1
