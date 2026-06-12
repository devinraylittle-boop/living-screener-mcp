# Tuesday Low-Token Runbook

Purpose: keep Living Screener operating through Tuesday with minimum Codex usage, clear manual controls, and no guessing.

## Current Operating Mode

- Render scanner: live at https://living-screener-mcp.onrender.com
- Dashboard: https://living-screener-mcp.onrender.com/ops/trading-monster-dashboard?account_value=100&buying_power=100&max_daily_loss=20&format=html
- Local bridge: broker-connected stock execution from this laptop
- Stocks: enabled
- Options: watch only until Robinhood exposes option review/place tools in this Codex session
- Crypto: disabled
- Paper: disabled for live stock bridge; scanner logs continue
- Max daily loss: 20 dollars
- Max order notional: 15 dollars
- Max open positions: 2
- Max trades per day: 10
- Min score: 70
- Min relative volume: 0.35
- Max spread: 45 bps
- Scan interval: 45 seconds
- Stock risk model: planned stop distance, not full stock notional

## Check Status Without Codex

Run from:

```powershell
cd "C:\Users\devin\OneDrive\Documents\Screener\living-screener-mcp-full-crypto-universe-20260612-000000"
```

Bridge process:

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*stock_bridge_loop.py*' -or $_.CommandLine -like '*start_stock_bridge_loop.ps1*' } | Select-Object ProcessId,ParentProcessId,Name,CommandLine | Format-List
```

Notes:

- Seeing `powershell.exe` -> Windows Python shim -> real Python is normal.
- Multiple unrelated `stock_bridge_loop.py` process trees would be a red flag.

Recent decisions:

```powershell
Get-Content .\data\stock_bridge_loop.jsonl -Tail 50
```

Bridge state:

```powershell
Get-Content .\data\stock_bridge_state.json
```

Errors:

```powershell
Get-Content .\data\stock_bridge_process.err.log -Tail 80
```

Robinhood app remains the source of truth for final account value, open positions, and filled orders.

## Stop Trading Immediately

Stop the local broker bridge:

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*stock_bridge_loop.py*' -or $_.CommandLine -like '*start_stock_bridge_loop.ps1*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

Disable scanner-side autonomy:

```text
https://living-screener-mcp.onrender.com/ops/autonomy-control?autonomous_enabled=false&stocks_enabled=false&options_enabled=false&crypto_enabled=false&paper_trading_enabled=false&live_handoff_enabled=false&format=html
```

## Restart Stock Autonomy

Use this current wider operating profile:

```powershell
cd "C:\Users\devin\OneDrive\Documents\Screener\living-screener-mcp-full-crypto-universe-20260612-000000"
$env:STOCK_BRIDGE_LIVE_AUTH="ENABLE_AGENTIC_STOCK_BRIDGE"
.\tools\start_stock_bridge_loop.ps1 -Live -MaxOrderNotional 15 -MaxDailyLoss 20 -MinScore 70 -MinRelativeVolume 0.35 -MaxSpreadBps 45 -AllowedBrokerAlertTypes "EQUITY_SUITABILITY" -IntervalSeconds 45
```

Re-arm scanner-side stock autonomy:

```text
https://living-screener-mcp.onrender.com/ops/autonomy-control?autonomous_enabled=true&stocks_enabled=true&options_enabled=false&crypto_enabled=false&paper_trading_enabled=false&live_handoff_enabled=false&max_daily_loss=20&max_crypto_cash=0&format=html
```

## Parameter Presets

Conservative:

```powershell
.\tools\start_stock_bridge_loop.ps1 -Live -MaxOrderNotional 5 -MaxDailyLoss 20 -MinScore 94 -MinRelativeVolume 1.15 -MaxSpreadBps 20 -AllowedBrokerAlertTypes "EQUITY_SUITABILITY" -IntervalSeconds 90
```

Balanced:

```powershell
.\tools\start_stock_bridge_loop.ps1 -Live -MaxOrderNotional 10 -MaxDailyLoss 20 -MinScore 76 -MinRelativeVolume 0.45 -MaxSpreadBps 35 -AllowedBrokerAlertTypes "EQUITY_SUITABILITY" -IntervalSeconds 60
```

More aggressive, still capped:

```powershell
.\tools\start_stock_bridge_loop.ps1 -Live -MaxOrderNotional 15 -MaxDailyLoss 20 -MinScore 70 -MinRelativeVolume 0.35 -MaxSpreadBps 45 -AllowedBrokerAlertTypes "EQUITY_SUITABILITY" -IntervalSeconds 45
```

Before switching presets, stop the current bridge process first.

## Options Watch

Options execution is not armed until Robinhood exposes all required tools:

- `get_option_chains`
- `get_option_quotes`
- `review_option_order`
- `place_option_order`

Low-token Codex prompt once or twice per day:

```text
OPTIONS TOOL CHECK ONLY: tell me whether Robinhood exposes get_option_chains, get_option_quotes, review_option_order, and place_option_order in this session. No strategy analysis unless changed.
```

If the tools appear, do not enable options live immediately. First run:

1. chain/quote validation
2. contract liquidity checks
3. review-only option ticket
4. one tiny live option order only if all gates pass

## Low-Token Communication Rules

Use Codex only for:

- options tool availability changed
- bridge errors appear in `stock_bridge_process.err.log`
- state says `halted: true`
- Robinhood shows unexpected position/order behavior
- end-of-day performance review
- parameter changes that materially alter risk

Suggested status prompt:

```text
STATUS ONLY: inspect bridge logs/state and summarize current positions, closed trades, blockers, and whether intervention is needed. Keep it short.
```

Suggested tuning prompt:

```text
TUNE ONLY: use today's JSONL bridge log to recommend one conservative parameter change and one aggressive parameter change. Do not edit files unless I confirm.
```

## Tuesday Review

On Tuesday, export or inspect:

- closed trades
- open-position management outcomes
- rejected candidates
- broker rejections
- stop-loss exits versus later recovery
- take-profit exits versus continuation
- spread/slippage at entry
- average hold time
- win rate and expectancy

Then decide whether to:

- increase max order notional
- adjust stop/take-profit distance
- add trailing exits
- allow more open positions
- arm options, if tools and account permissions are ready
