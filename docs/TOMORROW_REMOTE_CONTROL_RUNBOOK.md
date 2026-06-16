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

