$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$exampleEnvPath = Join-Path $repoRoot ".env.example"
$envPath = Join-Path $repoRoot ".env.local"

& (Join-Path $scriptDir "load_local_env.ps1") -Path $exampleEnvPath
& (Join-Path $scriptDir "load_local_env.ps1") -Path $envPath

Push-Location $repoRoot
try {
    python tools\stage5_readiness_report.py
}
finally {
    Pop-Location
}
