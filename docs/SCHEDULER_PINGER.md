# Scheduler Pinger

Build: `2026.06.11-broker-proof-bridge`

This package adds two ways to keep Living Screener awake and logging review-only scan evidence.

## What It Does

- Calls `/health/full` to verify the deployed build and safety surface.
- Calls `/ops/autonomous-morning-scan` on a repeating cadence.
- Lets the app log truth-source status, market-data health, catalyst context, phase-aware heartbeat output, and next action.
- Never places, submits, simulates, modifies, or cancels broker orders.

## Cloud Pinger

File: `.github/workflows/morning-autonomous-pinger.yml`

The workflow runs on weekdays every 5 minutes from roughly 7:00am to 4:00pm Central during U.S. daylight time.

After upload to GitHub:

1. Open the repository on GitHub.
2. Go to **Actions**.
3. Enable workflows if GitHub asks.
4. Open **Living Screener Morning Pinger**.
5. Use **Run workflow** once to test it manually.

The scheduled workflow may not run at an exact second. That is fine. It is a pinger and evidence collector, not an execution system.

## Local Backup Pinger

File: `tools/morning_pinger.ps1`

Run this from PowerShell if you want a local tab/window keeping the scanner active:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\morning_pinger.ps1
```

For a one-time check:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\morning_pinger.ps1 -Once
```

## Safety

The pinger must never be treated as trade approval.

Hard stops:

- No market orders.
- No broker action from this MCP.
- No cash review while market data health is blocked.
- No cash review on unresolved catalyst blocks.
- No options cash review without fresh broker-visible bid, ask, volume, open interest, DTE, strike, and max loss.
- No stale pending buy trusted after 60 seconds without recheck.

## Morning Validation

After deployment:

```text
/version
/tools
/health/full?expected_build_version=2026.06.11-broker-proof-bridge
/ops/autonomous-morning-scan?format=html
```

Expected:

- Build version: `2026.06.11-broker-proof-bridge`
- Tool count: `81`
- Full health: `OK`
- Autonomous scan returns a review-only status and a next refresh interval.
