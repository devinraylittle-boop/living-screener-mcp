# Tomorrow Remote Control Runbook

## Status

Ask:

```text
check Alpaca paper status
```

Command:

```powershell
powershell -ExecutionPolicy Bypass -File tools\status_alpaca_paper.ps1
```

## Start Or Resume Paper Trading

Ask:

```text
start Alpaca paper trading
```

Command:

```powershell
powershell -ExecutionPolicy Bypass -File tools\start_alpaca_paper_indefinite.ps1
```

## Stop Paper Trading

Ask:

```text
stop Alpaca paper trading
```

Command:

```powershell
powershell -ExecutionPolicy Bypass -File tools\stop_alpaca_paper.ps1
```

## Start Watchdog

Ask:

```text
start Alpaca paper watchdog
```

Command:

```powershell
powershell -ExecutionPolicy Bypass -File tools\watch_alpaca_paper_bridge.ps1
```

## Logs

Bridge log:

```text
data\stock_bridge_loop.jsonl
```

Paper process stdout/stderr:

```text
data\alpaca_paper_indefinite.out.log
data\alpaca_paper_indefinite.err.log
```

Watchdog log:

```text
data\watchdog_alpaca_paper.log
```

## Safety

This controls Alpaca paper only. It does not enable live-cash Stage 4 or Stage 5 autonomy.

Live cash remains blocked except human-approved Stage 3 Robinhood equity trades.
# Paper Promotion Evidence

Check whether the active paper lane has enough promotion-grade evidence:

```powershell
powershell -ExecutionPolicy Bypass -File tools\status_paper_lifecycle.ps1
```

This report is evidence only. `PAPER_PROMOTION_BLOCKED` means keep paper trading and continue collecting closed paper trades until the configured readiness gates pass.

# Stage 3 Human-Approved Live Lane

Check Stage 3 code readiness:

```powershell
powershell -ExecutionPolicy Bypass -File tools\status_stage3.ps1
```

Stage 3 is limited to small, human-approved Robinhood equity orders only:

- max order notional: $10
- max daily loss: $5
- human approval required for every live order
- Alpaca remains paper-only in this package
- Stage 4/5 autonomous live trading remains blocked

Emergency stop for a local Robinhood stock bridge:

```powershell
powershell -ExecutionPolicy Bypass -File tools\stop_stock_bridge.ps1
```

# Stage 4 Limited Autonomous Live Readiness

Check Stage 4 readiness:

```powershell
powershell -ExecutionPolicy Bypass -File tools\status_stage4.ps1
```

Expected current status is `STAGE4_CODE_READY_RUNTIME_BLOCKED`.

Stage 4 live autonomy must stay blocked until every runtime gate is green:

- paper promotion reaches the configured minimum sample size and quality gates
- broker reconciliation is current and clean
- no duplicate open orders exist
- kill switches are present
- external alerting is live
- secrets rotation is confirmed

The Stage 4 report is read-only. It cannot place orders.

# Stage 5 Full Autonomous Readiness

Check Stage 5 readiness:

```powershell
powershell -ExecutionPolicy Bypass -File tools\status_stage5.ps1
```

Check the uploaded full-autonomy execution order:

```powershell
powershell -ExecutionPolicy Bypass -File tools\status_execution_order.ps1
```

Expected current status is `STAGE5_LOCKED_PAPER_ONLY`.

Expected final decision is `GO_ALPACA_PAPER_AUTONOMY_NO_GO_LIVE_CASH`.

This is intentional. If you are away from the computer, the system should protect the account by allowing Alpaca paper autonomy and refusing unsupervised live cash trading.

The current full-autonomy execution order has been completed for Alpaca paper autonomy. The remaining sample-size, market-day, reconciliation, alerting, secrets, and 90-day items are live-cash promotion gates, not blockers to the current paper-only package.

Stage 5 live autonomy requires all Stage 4 gates plus:

- 90-day clean record
- external monitoring
- monthly model review
- continuous broker reconciliation
- confirmed secrets rotation
- no unresolved live-position or open-order conflicts

If any critical check is red, do not enable live cash autonomy.
