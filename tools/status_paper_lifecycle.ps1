$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

Push-Location $repoRoot
try {
    python tools\paper_lifecycle_ledger.py --json
    if ($LASTEXITCODE -eq 2) {
        exit 0
    }
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}

