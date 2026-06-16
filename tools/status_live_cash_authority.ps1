$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$path = Join-Path $repoRoot "config\live_cash_authority_order.txt"

Push-Location $repoRoot
try {
    python tools\execution_order_validator.py --path $path
}
finally {
    Pop-Location
}
