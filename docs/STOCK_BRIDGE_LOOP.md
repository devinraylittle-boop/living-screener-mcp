# Stock Bridge Loop

The best first deployment target is the laptop, not public web hosting.

Reasons:

- The laptop already has Codex and the Robinhood Trading MCP configured.
- OAuth can complete locally in the browser.
- Broker credentials and tokens stay off Render and off shared hosting.
- The process can run continuously while plugged in, with logs written locally.

Render remains the scan/risk/journal brain. The local bridge is the execution hand.

## What It Does

`tools/stock_bridge_loop.py` runs this cycle:

1. Read portfolio, buying power, open orders, and positions from Robinhood MCP.
2. Manage open long stock positions with stop-loss/take-profit exits.
3. Pull a broad stock scan from Living Screener.
4. Select only long, tradeable, above-VWAP candidates that pass score, relative-volume, and spread filters.
5. Ask Living Screener for an immutable stock intent.
6. Review the order through Robinhood MCP.
7. In live mode only, place the order through Robinhood MCP.
8. Log the broker result back to `/trade/manual-action`.

## Safety Defaults

- Long equities only.
- Options disabled until Robinhood exposes option chain/quote/review/place/cancel tools.
- Crypto disabled.
- Default max order notional: `$5`.
- Default max daily loss: `$20`.
- Default max open positions: `2`.
- Default max trades per day: `10`.
- Default entry score: `76`.
- Default minimum relative volume: `0.45`.
- Default max spread: `35 bps`.
- Default stop-loss: `0.35%`.
- Default take-profit: `0.45%`.

## Dry Run

Dry run proves scan, OAuth, broker reads, tradability, quotes, intent, and review without placing orders:

```powershell
.\tools\start_stock_bridge_loop.ps1 -Once
```

## Live Run

Live mode requires standing authorization in the same PowerShell session:

```powershell
$env:STOCK_BRIDGE_LIVE_AUTH="ENABLE_AGENTIC_STOCK_BRIDGE"
.\tools\start_stock_bridge_loop.ps1 -Live
```

To run one live cycle:

```powershell
$env:STOCK_BRIDGE_LIVE_AUTH="ENABLE_AGENTIC_STOCK_BRIDGE"
.\tools\start_stock_bridge_loop.ps1 -Live -Once
```

## Logs

- Runtime log: `data/stock_bridge_loop.jsonl`
- State file: `data/stock_bridge_state.json`

## Hosting Later

Move this off the laptop only after the laptop version proves stable. A VPS is better than ordinary shared web hosting because it supports long-running processes, local encrypted token storage, restart policies, and process monitoring.
