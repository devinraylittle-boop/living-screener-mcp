$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

$env:ALPACA_EXPECTED_ENV = "live"
$env:ALPACA_BASE_URL = if ($env:ALPACA_LIVE_BASE_URL) { $env:ALPACA_LIVE_BASE_URL } else { "https://api.alpaca.markets" }
$env:ALPACA_API_KEY_ID = if ($env:ALPACA_LIVE_API_KEY_ID) { $env:ALPACA_LIVE_API_KEY_ID } else { "" }
$env:ALPACA_API_SECRET_KEY = if ($env:ALPACA_LIVE_API_SECRET_KEY) { $env:ALPACA_LIVE_API_SECRET_KEY } else { "" }

Push-Location $repoRoot
try {
    python tools\validate_alpaca_credentials.py
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
