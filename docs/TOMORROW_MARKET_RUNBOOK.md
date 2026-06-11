# Tomorrow Market Runbook

Build target: `2026.06.11-paper-exploration-v2`

This runbook keeps the day boring on purpose: validate first, observe first, review only, and never let urgency bypass the gates.

## 1. After Deploy

From the package folder:

```powershell
.\tools\watch_deploy.ps1
```

Pass condition:

```text
LIVE_VALIDATION_PASS
```

If it fails, do not run scans from ChatGPT yet. Fix the deploy/build mismatch first.

## 2. Market Morning Start

After live validation passes:

```powershell
.\tools\start_tomorrow.ps1
```

This opens the control pages. It does not run scans or broker actions.

## 3. ChatGPT Connector Check Prompt

Paste this into ChatGPT with the Living Screener app selected:

```text
Use Living Screener MCP. Confirm safety config first. Then call get_version and confirm build_version is 2026.06.11-paper-exploration-v2. Then call get_tomorrow_operator_brief and run_go_live_rehearsal with account_value=50 and include_market_check=false. Do not run a market scan yet. Report safety status, build version, tool count if available, and whether rehearsal is READY, CAUTION, or BLOCKED. Do not create a trade plan or perform any order action.
```

If the connector is not exposed, use the browser endpoints:

```text
https://living-screener-mcp.onrender.com/version
https://living-screener-mcp.onrender.com/tools
https://living-screener-mcp.onrender.com/release-manifest
https://living-screener-mcp.onrender.com/health/full?expected_build_version=2026.06.11-paper-exploration-v2
https://living-screener-mcp.onrender.com/ops/go-live-rehearsal?account_value=50&format=html
```

## 4. First 15-30 Minutes After Open

Do not force a trade during opening noise. Use observation first.

Prompt:

```text
Use Living Screener MCP. Confirm safety config first. Run market_open_observer on AMZN, SOFI, SHOP, XOM, LULU, AAPL, QQQ, IWM, MSFT, NVDA, AMD, META, AVGO, SMCI, RBLX, CVX, LLY, UNH, HOOD, TSLA with max_candidates=25. This is review-only. Report evidence scorecards, relative strength, VWAP alignment, false-positive penalties, and top observation candidates. Do not create a trade plan.
```

Fallback URL:

```text
https://living-screener-mcp.onrender.com/ops/market-open-observer?tickers=AMZN,SOFI,SHOP,XOM,LULU,AAPL,QQQ,IWM,MSFT,NVDA,AMD,META,AVGO,SMCI,RBLX,CVX,LLY,UNH,HOOD,TSLA&max_candidates=25&cadence_minutes=5&format=html
```

## 5. Scalp Scan Prompt

Use only after the open has stabilized enough to trust quotes.

```text
Use Living Screener MCP. Confirm safety config first. Run run_scalp_scan with tickers AMZN, SOFI, SHOP, XOM, LULU, AAPL, QQQ, IWM, MSFT, NVDA, AMD, META, AVGO, SMCI, RBLX, CVX, LLY, UNH, HOOD, TSLA and max_candidates=25. Only rank candidates with valid stock setup, clear direction, and small-account options gate ready after review_candidate_for_options. Do not rank OPTIONS_CHAIN_ACCEPTABLE alone. Report NO_TRADE_PLAN if no candidate clears both stock and small-account options gates.
```

Fallback URL:

```text
https://living-screener-mcp.onrender.com/ops/live-review-cycle?tickers=AMZN,SOFI,SHOP,XOM,LULU,AAPL,QQQ,IWM,MSFT,NVDA,AMD,META,AVGO,SMCI,RBLX,CVX,LLY,UNH,HOOD,TSLA&account_value=50&max_candidates=25&review_top_n=8&max_contract_price=1.00&format=html
```

## 6. Candidate Review Prompt

Use only for a specific ticker that cleared the stock gate.

```text
Use Living Screener MCP. Confirm safety config first. Review [TICKER] for [call_or_put] using review_candidate_for_options in scalp_review mode, max_contract_price=1.00. Report stock setup quality, selected contract, spread, volume, open interest, DTE, max loss, small-account status, warnings, and blocking reasons. If the result is not SMALL_ACCOUNT_SCALP_ACCEPTABLE or REVIEW_ONLY_OPTIONS_READY with a selected contract, return NO_TRADE_PLAN.
```

## 7. Manual Broker Snapshot

If Robinhood shows different live option data than the screener, use the manual form:

```text
https://living-screener-mcp.onrender.com/trade/manual-form?format=html
```

Required broker-visible fields:

```text
ticker
contract symbol
call or put
bid
ask
volume
open interest
DTE
strike
underlying price
VWAP if visible
account value
```

Decision rule:

```text
If the manual snapshot gate blocks, pass.
If the spread widens, pass.
If VWAP alignment breaks, pass.
If relative strength weakens or setup chops sideways, pass.
If risk guard blocks, pass.
```

## 8. Paper/Manual Review Logging

If a review focus is created:

```text
Use Living Screener MCP. Confirm safety config first. Log this as a review-only decision, not a broker order. Include ticker, direction, selected contract, bid, ask, max loss, stock setup score, warnings, invalidation rules, and no broker action taken.
```

If a paper/manual entry is later recorded:

```text
Use Living Screener MCP. Confirm safety config first. Log the manual option paper entry with exact fill price, quantity, contract, direction, and reason. Then export a journal checkpoint. Do not treat this as broker execution.
```

## 9. Follow-Up Learning

After 15, 30, and 60 minutes:

```text
Use Living Screener MCP. Confirm safety config first. Check review outcome for [TICKER] [direction] using the original entry reference and timestamp. Classify the outcome as HELPED, HURT, FLAT, or UNAVAILABLE. Summarize what the setup taught us and whether any rule proposal should be researched. Do not change live rules without backtesting.
```

## 10. Hard Stops

No exceptions:

```text
No market orders.
No 0DTE unless explicitly enabled and separately validated.
No trade from stale quote/candle data.
No trade from options-chain quality alone.
No trade if stock setup and options contract disagree.
No trade if max loss exceeds small-account comfort.
No trade if the manual broker snapshot conflicts with the screener.
No broker action unless the user makes a separate manual broker decision.
```
