# Optimized Autonomous Package Runbook

## Package Purpose

This package is the clean operating base for the autonomous trading system.

It is optimized for:

- Aggressive Alpaca paper trading.
- Research and counterfactual learning.
- Guarded Robinhood Stage 3 equity live trades.
- Strict refusal of Stage 4/Stage 5 live autonomy until readiness gates pass.

It is not optimized for:

- Unlimited live trading.
- Autonomous live options.
- Autonomous live crypto.
- Untested strategy promotion.
- Bypassing risk gates.

## One-Minute Status

Current classification: limited live-trading ready.

Allowed now:

- Stage 2 Alpaca paper automation.
- Stage 3 small, human-approved Robinhood equity trades.

Blocked now:

- Stage 4 limited autonomous live trading.
- Stage 5 full autonomous live trading.
- Live options autonomy.
- Live crypto autonomy.

The enforcement source of truth is `config/autonomous_readiness_gates.json`.

## Clean Package Contents

Core source:

- `app/`
- `tools/`
- `tests/`
- `config/`
- `docs/`
- `README.md`
- deployment files

Important configs:

- `config/autonomous_readiness_gates.json`
- `config/anomaly_strategy_registry.json`
- `config/optimized_package_manifest.json`

Important runbooks:

- `docs/PREMIUM_AUTONOMOUS_TRADING_SYSTEM_PLAN.md`
- `docs/AUTONOMOUS_TRADING_ENABLEMENT_PLAN.md`
- `docs/STOCK_BRIDGE_LOOP.md`
- `docs/BROKER_CREDENTIAL_SETUP.md`
- `docs/ANOMALY_STRATEGY_ROADMAP.md`
- `docs/BAD_SETUP_LEARNING_SYSTEM.md`
- `docs/TOMORROW_REMOTE_CONTROL_RUNBOOK.md`

Excluded from clean distribution:

- Python caches.
- Pytest cache.
- Local secrets.
- Runtime SQLite databases.
- Old bridge stdout/stderr logs.
- Prior package archives.

## Alpaca Paper Validation

Set credentials only in the current shell:

```powershell
$env:ALPACA_BASE_URL="https://paper-api.alpaca.markets"
$env:ALPACA_EXPECTED_ENV="paper"
$env:ALPACA_API_KEY_ID="<paper key id>"
$env:ALPACA_API_SECRET_KEY="<paper secret key>"
python tools\validate_alpaca_credentials.py
```

Acceptance criteria:

- `status` is `ALPACA_VALIDATION_READY`.
- `endpoint_environment` is `paper`.
- `account_ready` is `true`.
- Secrets are not printed.

## Alpaca Paper Dry Run

```powershell
$env:ALPACA_BASE_URL="https://paper-api.alpaca.markets"
$env:ALPACA_DATA_URL="https://data.alpaca.markets"
$env:ALPACA_API_KEY_ID="<paper key id>"
$env:ALPACA_API_SECRET_KEY="<paper secret key>"
python tools\stock_bridge_loop.py --broker alpaca --once
```

This proves scanner, risk checks, and broker route without placing even paper orders.

## Alpaca Paper Execution

Use paper execution only after dry-run logs are clean:

```powershell
$env:ALPACA_BASE_URL="https://paper-api.alpaca.markets"
$env:ALPACA_DATA_URL="https://data.alpaca.markets"
$env:ALPACA_API_KEY_ID="<paper key id>"
$env:ALPACA_API_SECRET_KEY="<paper secret key>"
$env:AUTONOMY_STAGE="stage_2_paper_trading_automation"
python tools\stock_bridge_loop.py --broker alpaca --live --once
```

In this command, `--live` means "submit to the selected broker endpoint." With the Alpaca paper endpoint, submitted orders are paper orders.

## Robinhood Guarded Live Equity

Robinhood live remains Stage 3 only:

```powershell
$env:AUTONOMY_STAGE="stage_3_human_approved_live_trades"
$env:STOCK_BRIDGE_LIVE_AUTH="ENABLE_AGENTIC_STOCK_BRIDGE"
python tools\stock_bridge_loop.py --broker robinhood --live --once
```

This path refuses Stage 4 and Stage 5 autonomy.

## Proof That Full Autonomy Is Blocked

```powershell
$env:AUTONOMY_STAGE="stage_5_full_autonomous_with_strict_caps"
$env:STOCK_BRIDGE_LIVE_AUTH="ENABLE_AGENTIC_STOCK_BRIDGE"
python tools\stock_bridge_loop.py --broker robinhood --live --once
```

Expected result:

```text
Live mode refused.
```

## Validation Command

```powershell
python -m unittest tests.test_stock_bridge_live_stage_gate tests.test_autonomous_readiness_gates tests.test_anomaly_strategy_registry tests.test_alpaca_execution_router
```

Acceptance criteria:

- All tests pass.
- Stage 5 live startup is refused.
- Alpaca paper base URL accepts host or `/v2` suffix.
- Strategy registry remains live-safe by default.

## Next Required Build Work

To earn Stage 4:

1. Build paper lifecycle ledger.
2. Build broker reconciliation service.
3. Build external alerting and heartbeat.
4. Build operator kill switch.
5. Rotate secrets and document secret storage.
6. Capture at least 100 closed paper trades across at least 20 market days.
7. Produce walk-forward validation and strategy-promotion reports.
