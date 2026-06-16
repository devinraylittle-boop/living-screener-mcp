$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

Push-Location $repoRoot
try {
    python tools\stage3_readiness_report.py
}
finally {
    Pop-Location
}

