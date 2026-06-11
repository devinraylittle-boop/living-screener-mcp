# AI Continuity Protocol

Purpose: make every future Codex or ChatGPT session able to resume the Living Screener work quickly, safely, and with minimal context loss.

## Non-Negotiable Safety State

- Living Screener MCP is review-only.
- It cannot place, cancel, modify, submit, or simulate broker orders.
- Market orders are not allowed.
- Manual approval phrase remains `APPROVED EXACT ORDER`.
- Pending buy orders older than 60 seconds must be rechecked before being trusted.
- Stock setup alone is not enough.
- Options-chain quality alone is not enough.
- A broker-visible option snapshot must match or improve the reviewed contract before any manual broker-side action.
- Rule changes from learning output are proposals only until backtested and manually approved.

## Current Live Target

- Render URL: `https://living-screener-mcp.onrender.com`
- Expected build: `2026.06.11-autonomous-firewall`
- Expected tool count: 67
- Required pass signal: `LIVE_VALIDATION_PASS`
- Tomorrow start signal: `START_TOMORROW_READY`

## First Commands For Any New Codex Session

From the package folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\agent_status_snapshot.ps1
powershell -ExecutionPolicy Bypass -File .\tools\validate_live.ps1
```

If preparing for market open:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\start_tomorrow.ps1
```

## First Checks For Any New ChatGPT Session

Ask ChatGPT to do this before analysis:

1. Confirm the connected Living Screener MCP app is callable.
2. Call `get_version`.
3. Confirm build is `2026.06.11-autonomous-firewall`.
4. Call `get_safety_config`.
5. Confirm review-only and no place/cancel capability.
6. Only then run scans or reviews.

If the connector is not exposed, use public fallback endpoints:

- `/version`
- `/health/full?expected_build_version=2026.06.11-autonomous-firewall`
- `/debug/tool-manifest`
- `/debug/scan-schema?expected_build_version=2026.06.11-autonomous-firewall`
- `/risk/failure-mode-audit`

If endpoint access fails from ChatGPT runtime, report exactly:

`CONNECTOR_NOT_EXPOSED_IN_THIS_TURN`

Do not claim the app is broken unless the user or Codex verifies the public endpoint fails locally/browser-side too.

## Normal Market Workflow

1. Validate build and safety.
2. Run go-live rehearsal.
3. Run market-open observer.
4. Run live review cycle only after liquidity has stabilized.
5. Rank only candidates that clear:
   - stock setup quality
   - valid direction
   - options-chain quality
   - `SMALL_ACCOUNT_SCALP_ACCEPTABLE`
   - session risk guard
   - broker-visible manual snapshot
6. If the user manually acts in broker, log the action.
7. If paper-tracking, log paper entry, watch position, close paper trade, classify result.
8. Export journal checkpoint after meaningful events.

## What To Improve Next

Highest priority:

1. Add broker-visible snapshot/fill/slippage comparison to every manual action journal entry.
2. Add confidence-bucket outcome reporting to the learning dashboard.
3. Add a walk-forward validation report before changing live thresholds.
4. Add morning broker-balance/open-position confirmation to the launch checklist.

Do not prioritize flashy new indicators before these controls. Accuracy improves through replayable evidence.




