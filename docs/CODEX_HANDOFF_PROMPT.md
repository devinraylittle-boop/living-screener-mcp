# Codex Handoff Prompt

Paste this into a fresh Codex session if this conversation runs out of context.

```text
We are working on Living Screener MCP in:
C:\Users\devin\OneDrive\Documents\Screener

Use the latest package folder unless I specify otherwise:
living-screener-mcp-options-provider-20260610-223000

The live Render app is:
https://living-screener-mcp.onrender.com

Expected build:
2026.06.11-event-radar-broad-scan

First, run:
powershell -ExecutionPolicy Bypass -File .\tools\agent_status_snapshot.ps1
powershell -ExecutionPolicy Bypass -File .\tools\validate_live.ps1

Safety is non-negotiable:
- review-only
- no broker order placement
- no broker cancellation
- no market orders
- no auto-applied learning proposals
- pending buys older than 60 seconds must be rechecked

Primary objective:
Prepare and operate a review-only stock/options screener for tomorrow’s market session. Accuracy is priority one, profit is priority two. The system should scan, review, validate, log, paper-track, classify outcomes, and improve by evidence. It must not execute broker actions.

Most recent improvement:
Added failure-mode audit build with:
- get_failure_mode_audit tool
- /risk/failure-mode-audit endpoint
- expected tool count 67
- validation script updated
- start_tomorrow helper updated

Next useful improvements, in order:
1. Add broker-visible snapshot/fill/slippage comparison to every manual action journal entry.
2. Add confidence-bucket outcome reporting to learning dashboard.
3. Add walk-forward validation report before changing live thresholds.
4. Add morning broker-balance/open-position confirmation to launch checklist.

Before coding, verify the live app and read docs/AI_CONTINUITY_PROTOCOL.md.
```




