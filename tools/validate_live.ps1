param(
    [string]$BaseUrl = "https://living-screener-mcp.onrender.com",
    [string]$ExpectedBuild = "2026.06.11-event-volatility",
    [int]$AccountValue = 50,
    [int]$TimeoutSeconds = 20
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Net.Http

$handler = [System.Net.Http.HttpClientHandler]::new()
$client = [System.Net.Http.HttpClient]::new($handler)
$client.Timeout = [TimeSpan]::FromSeconds($TimeoutSeconds)

function Invoke-Check {
    param(
        [string]$Name,
        [string]$Path,
        [string]$MustContain = ""
    )

    $uri = "$BaseUrl$Path"
    try {
        $response = $client.GetAsync($uri).GetAwaiter().GetResult()
        $content = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        $statusCode = [int]$response.StatusCode
        $ok = $statusCode -eq 200
        if ($MustContain -ne "") {
            $ok = $ok -and $content.Contains($MustContain)
        }
        [pscustomobject]@{
            Name = $Name
            StatusCode = $statusCode
            Pass = $ok
            Url = $uri
            Note = if ($ok) { "OK" } else { "Expected text not found: $MustContain" }
        }
    }
    catch {
        [pscustomobject]@{
            Name = $Name
            StatusCode = "ERROR"
            Pass = $false
            Url = $uri
            Note = $_.Exception.Message
        }
    }
}

$checks = @(
    Invoke-Check -Name "Version" -Path "/version" -MustContain $ExpectedBuild
    Invoke-Check -Name "Tools" -Path "/tools" -MustContain "run_go_live_rehearsal"
    Invoke-Check -Name "Release manifest" -Path "/release-manifest" -MustContain $ExpectedBuild
    Invoke-Check -Name "Full health" -Path "/health/full?expected_build_version=$ExpectedBuild" -MustContain '"status":"OK"'
    Invoke-Check -Name "Root operator brief" -Path "/" -MustContain "Tomorrow Operator Brief"
    Invoke-Check -Name "Go-live rehearsal" -Path "/ops/go-live-rehearsal?account_value=$AccountValue&format=html" -MustContain "Go-Live Rehearsal"
    Invoke-Check -Name "Manual snapshot form" -Path "/trade/manual-form?format=html" -MustContain "Manual Snapshot Form"
    Invoke-Check -Name "Failure-mode audit" -Path "/risk/failure-mode-audit?format=html" -MustContain "Failure-Mode Audit"
)

$checks | Format-Table Name,StatusCode,Pass,Note -AutoSize

if ($checks.Pass -contains $false) {
    Write-Host ""
    $checks | Where-Object { -not $_.Pass } | ForEach-Object {
        Write-Host "$($_.Name): $($_.Url)"
        Write-Host "  $($_.Note)"
    }
    Write-Host ""
    Write-Host "LIVE_VALIDATION_FAILED"
    exit 1
}

Write-Host ""
Write-Host "LIVE_VALIDATION_PASS"



