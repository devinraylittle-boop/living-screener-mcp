param(
    [string]$BaseUrl = "https://living-screener-mcp.onrender.com",
    [string]$ExpectedBuild = "2026.06.11-three-loss-guard",
    [int]$TimeoutSeconds = 20
)

$ErrorActionPreference = "Stop"

function Get-Json {
    param([string]$Path)
    Invoke-RestMethod -Uri "$BaseUrl$Path" -TimeoutSec $TimeoutSeconds
}

$version = Get-Json "/version"
$tools = Get-Json "/tools"
$health = Get-Json "/health/full?expected_build_version=$ExpectedBuild"
$safety = Get-Json "/safety"
$audit = Get-Json "/risk/failure-mode-audit"
$paper = Get-Json "/paper/options/summary"
$learning = Get-Json "/learning/dashboard"

$snapshot = [pscustomobject]@{
    timestamp_utc = (Get-Date).ToUniversalTime().ToString("s") + "Z"
    base_url = $BaseUrl
    expected_build = $ExpectedBuild
    live_build = $version.build_version
    build_matches = $health.result.build_matches_expected
    tool_count = $tools.tool_count
    has_failure_mode_audit = ($tools.tools -contains "get_failure_mode_audit")
    health_status = $health.result.status
    review_only = $safety.review_only
    place_orders = $safety.place_orders
    market_orders_allowed = $safety.market_orders_allowed
    can_place_order_from_this_mcp = $safety.can_place_order_from_this_mcp
    can_cancel_order_from_this_mcp = $safety.can_cancel_order_from_this_mcp
    failure_mode_audit_status = $audit.result.status
    failure_mode_controls = @($audit.result.controls).Count
    paper_status = $paper.result.status
    paper_open_count = $paper.result.open_count
    learning_classification_counts = $learning.classification_counts
    next_priority = $audit.result.highest_priority_next
}

$snapshot | ConvertTo-Json -Depth 8



