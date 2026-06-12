param(
    [string]$BaseUrl = "https://living-screener-mcp.onrender.com",
    [string]$Symbols = "",
    [decimal]$AccountBalance = 5.00,
    [decimal]$BuyingPower = 5.00,
    [decimal]$IntendedCash = 5.00,
    [decimal]$MinOrderSize = 0.01,
    [decimal]$FeeBps = 20,
    [decimal]$SlippagePct = 0.00008,
    [decimal]$TargetProfitPct = 0.01,
    [decimal]$StopLossPct = 0.003,
    [decimal]$EmergencyMaxLoss = 2.00,
    [int]$BacktestSymbolLimit = 20,
    [int]$DefaultSleepSeconds = 300,
    [switch]$Once
)

$ErrorActionPreference = "Stop"

function Build-Query {
    param([hashtable]$Values)
    $pairs = foreach ($key in $Values.Keys) {
        "$([System.Uri]::EscapeDataString([string]$key))=$([System.Uri]::EscapeDataString([string]$Values[$key]))"
    }
    return ($pairs -join "&")
}

function Invoke-LivingScreenerJson {
    param([string]$Url)
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 90
    return $response.Content | ConvertFrom-Json
}

Write-Host "Living Screener crypto autonomous cycle pinger"
Write-Host "Base URL: $BaseUrl"
Write-Host "Execution mode: paper. This script does not place live exchange orders."
Write-Host ""

do {
    $values = @{
        account_balance = $AccountBalance
        buying_power = $BuyingPower
        intended_cash = $IntendedCash
        exchange_connected = "true"
        open_positions_checked = "true"
        open_position_count = 0
        open_orders_checked = "true"
        open_order_count = 0
        market_data_fresh = "true"
        order_book_fresh = "false"
        kill_switch_ready = "true"
        emergency_shutdown_ready = "true"
        daily_loss_lockout_clear = "true"
        journaling_ready = "true"
        min_order_size = $MinOrderSize
        fee_bps = $FeeBps
        slippage_pct = $SlippagePct
        target_profit_pct = $TargetProfitPct
        stop_loss_pct = $StopLossPct
        emergency_max_loss = $EmergencyMaxLoss
        execution_mode = "paper"
        backtest_symbol_limit = $BacktestSymbolLimit
        format = "json"
    }
    if ($Symbols.Trim() -ne "") {
        $values.symbols = $Symbols
    }

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    try {
        $url = "$BaseUrl/crypto/autonomous-cycle?$(Build-Query $values)"
        $payload = Invoke-LivingScreenerJson -Url $url
        $result = $payload.result
        Write-Host "[$timestamp] $($result.final_decision) | gate=$($result.gate_decision) | mode=$($result.execution_mode)"
        if ($result.new_entry) {
            Write-Host "  new_entry=$($result.new_entry.status) symbol=$($result.new_entry.symbol)"
        }
        if ($result.management_actions) {
            foreach ($action in $result.management_actions) {
                Write-Host "  action=$($action.action) symbol=$($action.symbol) reason=$($action.reason)"
            }
        }
        $sleepSeconds = $DefaultSleepSeconds
    } catch {
        Write-Host "[$timestamp] Crypto cycle ping failed: $($_.Exception.Message)"
        $sleepSeconds = $DefaultSleepSeconds
    }

    if (-not $Once) {
        Start-Sleep -Seconds $sleepSeconds
    }
} while (-not $Once)
