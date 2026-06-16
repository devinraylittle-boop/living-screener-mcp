param(
    [string]$PackageName = "living-screener-autonomous-trading-optimized-20260616"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$distDir = Join-Path $repoRoot "dist"
$stagingDir = Join-Path $distDir $PackageName
$zipPath = Join-Path $distDir "$PackageName.zip"

$resolvedRepo = (Resolve-Path -LiteralPath $repoRoot).Path

if (Test-Path -LiteralPath $stagingDir) {
    $resolvedStage = (Resolve-Path -LiteralPath $stagingDir).Path
    if (-not $resolvedStage.StartsWith($resolvedRepo, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove staging path outside repo: $resolvedStage"
    }
    Remove-Item -LiteralPath $stagingDir -Recurse -Force
}

if (Test-Path -LiteralPath $zipPath) {
    $resolvedZip = (Resolve-Path -LiteralPath $zipPath).Path
    if (-not $resolvedZip.StartsWith($resolvedRepo, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove zip path outside repo: $resolvedZip"
    }
    Remove-Item -LiteralPath $zipPath -Force
}

New-Item -ItemType Directory -Force -Path $stagingDir | Out-Null

$excludeDirectoryNames = @(
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    "dist"
)

$excludeFilePatterns = @(
    "*.pyc",
    ".env",
    ".env.local",
    "robinhood-mcp-login.log",
    "living-screener-mcp-*.zip",
    "data\*.sqlite3",
    "data\*.sqlite3-*",
    "data\stock_bridge_*.out.log",
    "data\stock_bridge_*.err.log",
    "data\alpaca_paper_*.out.log",
    "data\alpaca_paper_*.err.log",
    "data\watchdog_*.log",
    "data\watchdog_*.out.log",
    "data\watchdog_*.err.log"
)

function Get-RelativeRepoPath {
    param([string]$Path)

    $full = (Resolve-Path -LiteralPath $Path).Path
    if (-not $full.StartsWith($resolvedRepo, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside repo: $full"
    }
    return $full.Substring($resolvedRepo.Length).TrimStart('\', '/')
}

function Test-ExcludedPath {
    param([string]$Path)

    $relative = Get-RelativeRepoPath -Path $Path
    $parts = $relative -split '[\\/]'
    foreach ($part in $parts) {
        if ($excludeDirectoryNames -contains $part) {
            return $true
        }
    }
    foreach ($pattern in $excludeFilePatterns) {
        if ($relative -like $pattern) {
            return $true
        }
    }
    return $false
}

$items = Get-ChildItem -LiteralPath $repoRoot -Recurse -Force | Where-Object {
    -not (Test-ExcludedPath -Path $_.FullName)
}

foreach ($item in $items) {
    $relative = Get-RelativeRepoPath -Path $item.FullName
    $destination = Join-Path $stagingDir $relative
    if ($item.PSIsContainer) {
        New-Item -ItemType Directory -Force -Path $destination | Out-Null
    } else {
        $parent = Split-Path -Parent $destination
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
        Copy-Item -LiteralPath $item.FullName -Destination $destination -Force
    }
}

Compress-Archive -Path (Join-Path $stagingDir "*") -DestinationPath $zipPath -Force

[pscustomobject]@{
    PackageDirectory = $stagingDir
    ZipPath = $zipPath
    FileCount = (Get-ChildItem -LiteralPath $stagingDir -Recurse -File | Measure-Object).Count
}
