# Premium Autonomous Trading System Plan

Date: 2026-06-16

## 1. Executive Summary

Readiness classification: limited live-trading ready.

This system is not ready for full autonomous live trading. It is ready for aggressive Alpaca paper trading and very small, human-approved Robinhood equity live tests only.

Current proven state:

- Robinhood Agentic equity order review/place/cancel tools are available in this Codex session.
- A small RBLX live equity order was placed with a protective stop after explicit user authorization.
- Robinhood options and crypto execution tools are not exposed in the current MCP session.
- Alpaca paper credentials validated against `https://paper-api.alpaca.markets`.
- Alpaca paper account supports stock/options/crypto capability probes.
- Living Screener remains intentionally review/risk/journal focused; execution belongs in the local bridge.
- Paper telemetry is still too thin for live promotion of strategies.

Biggest blockers:

- No complete paper trade lifecycle dataset with enough closed trades.
- No first-class autonomous options or crypto selection/management loop.
- No persistent external observability/alerting stack.
- Risk controls exist, but readiness gates need to become machine-enforced everywhere.
- Secrets are still being handled manually in local shell sessions.
- Deployment is local-laptop oriented, which is acceptable for early proof but not production resilience.

Highest-impact upgrades:

1. Machine-enforced readiness gates and kill switches.
2. Paper/counterfactual ledger with lifecycle outcomes.
3. Broker reconciliation loop for positions, orders, buying power, and stops.
4. External alerting for process death, broker disconnects, drawdown, and stale data.
5. Secrets management and credential rotation.
6. Premium options data only after the paper framework proves strategy value.

## 2. Full System Audit

| Area | Rating | Assessment |
| --- | --- | --- |
| Strategy logic | Needs improvement | Scanner/risk logic exists, but strategy lanes are not yet validated by sufficient closed paper samples. |
| Signal generation | Needs improvement | Broad scans and anomaly roadmap exist; features need event flags, regime state, and strategy-specific snapshots. |
| Data quality | Critical weakness | Market data blocks have occurred; options and event data are incomplete. Need freshness, source, and fallback scoring. |
| Backtesting | Critical weakness | Methodology doc exists, but no robust walk-forward, slippage, gap-risk, or survivorship-bias-free harness yet. |
| Paper trading | Needs improvement | Alpaca paper is now validated; lifecycle ledger and outcome worker are not complete. |
| Execution engine | Needs improvement | Local bridge handles equity-first route. Options/crypto execution paths exist but autonomous management is not first-class. |
| Broker/API reliability | Needs improvement | Robinhood OAuth/MCP works locally; Alpaca paper works. Need reconnect logic, health checks, and broker status alarms. |
| Order management | Needs improvement | Entry/review/place flow exists. Need stronger partial-fill, cancel/replace, duplicate-order, and stop reconciliation. |
| Portfolio/risk management | Needs improvement | Basic per-order/day limits exist. Need portfolio exposure, correlation, weekly/monthly limits, and strategy allocations. |
| Position sizing | Critical weakness | Fixed small notionals are safe but not professional sizing. Need volatility-adjusted and account-risk sizing. |
| Stop-loss/take-profit logic | Needs improvement | Equity stop/take-profit logic exists in bridge; needs reconciliation and slippage-aware stop handling. |
| Drawdown controls | Needs improvement | Daily loss halt exists; weekly/monthly drawdown controls should be added. |
| Kill switches | Needs improvement | Local env gate exists. Need file/API kill switch, broker cancel-all, and alert-driven shutdown. |
| Logging | Acceptable | JSONL and SQLite events exist. Need structured event schema and retention policy. |
| Monitoring | Critical weakness | No external uptime/process/drawdown monitoring. |
| Alerts | Critical weakness | Need SMS/push/email alerts for critical states. |
| Security | Needs improvement | Keys are not committed, but manual paste/env handling is risky. Need `.env.local`, secret manager, rotation, and least privilege. |
| Compliance | Needs improvement | Need broker/API terms review, data vendor terms, tax export, and audit retention. |
| Deployment infrastructure | Needs improvement | Render brain plus local bridge is good for early stage. Need supervised process manager and backup host plan. |
| Human override process | Needs improvement | Manual phrases and Codex control exist; need one-button kill switch and runbook. |

## 3. Premium Upgrade Recommendations

Pricing basis checked 2026-06-16 from vendor pages. Treat costs as planning ranges, not commitments.

| Priority | Upgrade | Purpose | Cost range | Benefit | Complexity | Risk reduction | Performance potential | Required before live autonomous | Exact implementation instructions |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | External alerting and incident monitoring | Detect process death, stale data, drawdown, broker disconnects | Free-$35/mo | Stops silent failure | Low | High | Medium | Yes | Add health heartbeat endpoint, Better Stack/Sentry monitor, SMS/email alert rules, and drawdown alerts. |
| P0 | Machine-enforced readiness gates | Prevent unsafe stage promotion | Free | Turns policy into code | Low | High | Medium | Yes | Load `config/autonomous_readiness_gates.json` in bridge startup and before every order. Refuse live if gates fail. |
| P0 | Secrets hygiene and rotation | Reduce key exposure | Free-$10/mo initially | Prevents credential leakage | Low | High | None | Yes | Move credentials to local uncommitted `.env.local`; rotate pasted keys; never log secrets; restrict broker permissions. |
| P0 | Paper lifecycle ledger | Produce valid learning dataset | Free | Enables real promotion decisions | Medium | High | High | Yes | Add paper order/open/close/outcome tables; record entry, exit, slippage, MFE, MAE, setup, strategy id. |
| P1 | Broker reconciliation service | Detect mismatched orders/positions/stops | Free | Avoids orphaned risk | Medium | High | Medium | Yes | Poll broker positions/open orders; compare against internal journal; cancel/alert on inconsistencies. |
| P1 | Alpaca paper autonomous runner | Aggressive testbed for stocks/options/crypto | Free with Alpaca paper | Scales research safely | Medium | Medium | High | No for limited Robinhood manual, yes for strategy promotion | Run local bridge against paper endpoint; segregate paper state and cash state. |
| P1 | Tradier brokerage/API | Options data/trading lane | Lite/Pro/Pro Plus cost varies; current public plans show API access and Pro tiers around $10-$35/mo | Better options chain/quote access | Medium | Medium | High for options | Before options live | Open small account, connect token, implement read-only quote/chain adapter first, then paper/sandbox if available. |
| P1 | Lightweight VPS/process supervisor | Keep bridge running reliably | $5-$20/mo VPS or managed host | Improves uptime | Medium | Medium | Medium | Before unattended live | Use Windows Task Scheduler locally first; later deploy bridge to hardened VPS with encrypted secrets and restart policy. |
| P1 | Postgres storage | Durable event/journal storage | Free-$20/mo early | Safer than local SQLite for production analytics | Medium | Medium | Medium | Before full autonomous | Add Postgres URL option; migrate event tables; back up daily. |
| P2 | Premium market/options data | Improve quote quality and backtests | Free-$300+/mo depending provider | Better signal and slippage modeling | Medium-High | Medium | High | Before options promotion | Start with Alpaca/Tradier; add MarketData.app or Massive only if paper needs exceed free/broker data. |
| P2 | LLM/API workflow | Research, log analysis, code review, news summaries | Variable OpenAI API token cost | Faster review and anomaly triage | Medium | Medium | Medium | No | Use LLMs only for analysis and summarization; execution decisions must remain bounded by deterministic gates. |
| P2 | Sentry/Datadog-grade observability | Errors, traces, dashboards | Sentry has free/paid tiers; Datadog often starts per-host | Better root-cause analysis | Medium | Medium | Low | Before multi-host production | Add structured errors, heartbeat spans, and incident dashboards. |
| P3 | Direct exchange/microstructure feeds | Auction/depth strategies | High/vendor-specific | Enables institutional-grade signals | High | Low initially | High but premature | No | Delay until bar/minute strategies prove value. |

Source anchors:

- Alpaca paper/market data: `https://docs.alpaca.markets/us/docs/paper-trading`, `https://alpaca.markets/data`
- Tradier API/pricing: `https://docs.tradier.com/`, `https://tradier.com/individuals/pricing`
- OpenAI API pricing: `https://openai.com/api/pricing/`
- Render free hosting: `https://render.com/docs/free`
- Better Stack pricing: `https://betterstack.com/pricing`
- Sentry pricing: `https://sentry.io/pricing/`
- Datadog pricing: `https://www.datadoghq.com/pricing/`
- MarketData.app pricing: `https://www.marketdata.app/pricing/`
- Massive pricing: `https://massive.com/pricing`

## 4. Immediate Optimization Plan

### A. Today

| Owner | Action | Tools | Success criteria | Failure risk | Priority |
| --- | --- | --- | --- | --- | --- |
| Automation engineer | Add readiness gate config and validate it in tests | Python, JSON | Config parse test passes | Policy remains prose-only | P0 |
| Risk manager | Keep Robinhood live lane limited to human-approved small equities | Robinhood MCP, journal | No autonomous cash order without broker review and explicit gate | Accidental scope creep | P0 |
| Security reviewer | Rotate any keys pasted into chat and move future keys to local env only | Alpaca dashboard, local shell | Old keys invalidated, new keys not committed | Credential reuse | P0 |
| Quant engineer | Run Alpaca paper dry-run and log no-trade/ready states | Alpaca paper, bridge | Dry-run completes and logs decision | Paper lane unproven | P0 |
| Operator | Define one emergency shutdown command and one cancel-open-orders runbook | PowerShell, broker UI | Human can stop bridge in under 60 seconds | Slow response during failure | P0 |

### B. This Week

| Owner | Action | Tools | Success criteria | Failure risk | Priority |
| --- | --- | --- | --- | --- | --- |
| Automation engineer | Implement paper lifecycle ledger | SQLite/Postgres-ready schema | Every paper order has open/close/outcome | Learning data remains unusable | P0 |
| Risk manager | Add weekly/monthly drawdown and per-strategy allocation caps | Risk service, bridge | Live/paper orders rejected when limits hit | Overtrading after daily reset | P0 |
| SRE | Add heartbeat and external monitor | Better Stack/Sentry/cron | Alert fires on process death or stale heartbeat | Silent downtime | P0 |
| Broker engineer | Add reconciliation loop | Robinhood/Alpaca APIs | Internal journal matches broker state | Orphaned positions/stops | P0 |
| Quant engineer | Add event flags for earnings/news/macro windows | Calendar source, data service | Reversal strategy excludes event repricing | Fading real information | P1 |

### C. Next 30 Days

| Owner | Action | Tools | Success criteria | Failure risk | Priority |
| --- | --- | --- | --- | --- | --- |
| Quant engineer | Implement relative-volume breakout/failure paper lane | Scanner, Alpaca paper | 50+ paper/counterfactual samples | Strategy remains unmeasured | P1 |
| Quant engineer | Implement announcement-aware reversal paper lane | Event flags, scanner | 50+ event-filtered samples | Bad setup classification weak | P1 |
| Data engineer | Add Postgres-compatible event storage | SQLAlchemy or repository layer | SQLite dev + Postgres production both pass tests | Local data loss | P1 |
| Broker engineer | Connect Tradier read-only options data | Tradier token | Chain/quote adapter returns spread/volume/OI | Options lane blind | P1 |
| SRE | Add dashboard for health, P/L, drawdown, open orders | Render/local UI | One view shows system state | Operator misses risk | P1 |

### D. Next 90 Days

| Owner | Action | Tools | Success criteria | Failure risk | Priority |
| --- | --- | --- | --- | --- | --- |
| Quant lead | Walk-forward backtests for promoted strategies | Backtest harness | Untouched holdout and walk-forward report | Overfit strategy promotion | P1 |
| Risk manager | Model correlation/exposure caps | Risk engine | Orders sized by vol and correlation | Concentrated losses | P1 |
| Automation engineer | Stage 4 limited autonomous live lane | Bridge, gates, alerts | All gates pass for 20+ days before activation | Premature autonomy | P2 |
| Security reviewer | Hardening review | Secrets manager, OS firewall, broker settings | Least privilege and audit logs confirmed | Credential or host compromise | P2 |
| Quant engineer | PEAD/text shadow strategy | Earnings/text data | Shadow signal report with timestamp quality | Fake alpha from bad timestamps | P2 |

## 5. Autonomous Trading Readiness Checklist

Minimum standards before limited autonomous live:

- Backtests use no look-ahead bias.
- Signals are generated only after candle/event availability.
- Entries use executable future prices.
- Slippage, spread, and fees are modeled conservatively.
- Paper trading runs at least 20 distinct market days.
- Strategy has at least 100 closed paper trades before autonomous live consideration.
- Profit factor after costs is at least 1.2.
- Max paper drawdown is below 8%.
- Max risk per trade is no more than 0.5% of account equity in limited autonomous mode.
- Daily loss limit is no more than 2% of equity.
- Weekly loss limit is no more than 5% of equity.
- Monthly drawdown kill is 10% of equity.
- Max open positions starts at 2.
- Max exposure per single equity starts at 25% of allocated live sleeve.
- Broker disconnect blocks new orders.
- API failure blocks new orders and starts cooldown.
- Bad/stale data blocks new orders.
- Duplicate order guard checks symbol, side, open orders, and recent intent hash.
- Emergency shutdown cancels open entry orders and pauses new entries.
- Human approval required for all Stage 3 live orders.
- Stage 4 requires all gates in `config/autonomous_readiness_gates.json`.

## 6. Risk Management Framework

Position sizing:

- Base position size = allowed risk dollars / volatility stop distance.
- Cap by max notional, buying power, liquidity, and strategy allocation.
- Reduce size when realized volatility, spread, or correlation rises.
- Never size from account buying power alone.

Portfolio caps:

- Per-symbol exposure: 25% of live sleeve at Stage 4.
- Per-sector exposure: 40% of live sleeve at Stage 4.
- Per-strategy allocation: start 50% max to any one promoted strategy.
- Crypto/options require separate sleeves and cannot borrow equity risk budget silently.

Loss limits:

- Max loss per trade: 0.5% of equity in limited autonomous mode.
- Max daily loss: 2% of equity or configured USD cap, whichever is lower.
- Max weekly loss: 5% of equity.
- Max monthly drawdown: 10% of equity.

Circuit breakers:

- Three rejected broker orders in one session pause new entries.
- Two consecutive data-provider failures pause new entries.
- Any unreconciled live position pauses new entries.
- Any missing protective stop on a live long equity triggers alert and trade-management mode only.
- Spread beyond limit blocks entry.
- Quote age beyond limit blocks entry.

Recovery after shutdown:

1. Stop strategy loop.
2. Fetch broker positions and open orders.
3. Cancel stale entry orders.
4. Confirm protective exits for open risk.
5. Write incident report.
6. Require human review before re-enabling entries.

## 7. Execution Engine Requirements

Architecture requirements:

- Deterministic ticket builder.
- Immutable pre-trade intent hash.
- Broker review before place.
- Journal-first record before live place.
- Idempotent `ref_id` for order placement.
- Duplicate order prevention by symbol/side/intent/open orders.
- Partial-fill handling.
- Rejected-order handling.
- Position reconciliation after every cycle.
- Stop/target reconciliation for live positions.
- Retry logic only for safe read operations and explicitly idempotent writes.
- No blind retry of order placement without checking broker order state.

Allowed order types:

- Equity entry: marketable limit preferred.
- Equity stop: stop market or stop limit depending liquidity.
- Options: limit only.
- Crypto: limit only unless explicit market crypto gate is enabled in paper.

Latency requirements:

- Current system targets seconds-to-minutes strategies, not high-frequency trading.
- If a setup depends on sub-second fills, it is out of scope.

Audit trail:

- Raw candidate.
- Feature snapshot.
- Risk decision.
- Broker review result.
- Order ticket.
- Broker order id.
- Fill status.
- Position reconciliation.
- Exit decision and outcome.

## 8. AI/LLM Integration Plan

Safe uses:

- Strategy research.
- Code review.
- Log analysis.
- News and filing summarization.
- Trade journaling.
- Anomaly triage.
- Postmortem generation.
- Test generation.
- Operator briefings.

Unsafe uses:

- Unlimited discretionary trade placement.
- Bypassing risk gates.
- Increasing size without deterministic policy.
- Trading on unverified summaries.
- Modifying live credentials or broker settings without human review.

LLM execution rule:

AI may propose, explain, rank, and summarize. Deterministic code must enforce risk, sizing, broker review, order placement, and kill switches.

## 9. Security and Compliance Review

Security controls:

- Rotate keys pasted into chat.
- Store active keys only in uncommitted local env or a secret manager.
- Never log API keys, OAuth tokens, account secrets, or full bearer tokens.
- Restrict withdrawal permissions where broker supports it.
- Use separate paper/live credentials.
- Use broker account with limited funded balance for early live tests.
- Enable MFA on broker/data accounts.
- Use OS account lock and disk encryption on execution host.
- Keep Render/host secrets separate from local broker OAuth.

Compliance controls:

- Review broker terms for automated/agentic trading.
- Review data vendor terms for redistribution, caching, and derived data.
- Keep audit logs for orders, decisions, and user authorizations.
- Export trade history for tax reporting.
- Do not present paper results as guaranteed live performance.
- Respect pattern day trading, options approval, margin, and jurisdiction limits.

## 10. System Architecture Blueprint

Flow:

1. Data ingestion layer collects bars, quotes, event flags, options chain data, and broker account state.
2. Feature engine builds RVOL, VWAP, spread, volatility, event, sector, and anomaly features.
3. Signal engine ranks candidates by promoted strategy definitions.
4. Strategy engine converts signal into proposed action: avoid, paper, shadow, or live candidate.
5. Risk engine validates account state, exposure, loss limits, liquidity, data freshness, and strategy promotion.
6. Execution engine builds immutable ticket and intent hash.
7. Broker interface performs review, place, cancel, and reconciliation.
8. Database stores candidate, decision, review, order, fill, position, and outcome.
9. Monitoring dashboard displays health, drawdown, open risk, broker status, and recent decisions.
10. Alerting layer sends critical incidents.
11. Admin control panel exposes pause, resume, kill, and stage controls.
12. Human override can block entries, flatten risk, or force paper-only mode.

## 11. Implementation Instructions

Step 1: Enforce readiness gates.

- Build/configure: load `config/autonomous_readiness_gates.json` in bridge startup and pre-order checks.
- Why: prevents accidental stage escalation.
- Tools: Python `json`, existing bridge config.
- Acceptance: live order path refuses when required gate is false.
- Test: unit test each hard block.
- Rollback: revert to existing env live-auth gate only.

Step 2: Build paper lifecycle ledger.

- Build/configure: tables or JSONL schema for paper intents, orders, fills, exits, and outcomes.
- Why: no strategy can be promoted without closed-trade evidence.
- Tools: SQLite repository now, Postgres-compatible schema later.
- Acceptance: every paper order has an outcome or explicit open status.
- Test: simulate open, partial fill, close, no-fill, and timeout.
- Rollback: keep current journal path read-only while schema stabilizes.

Step 3: Add broker reconciliation.

- Build/configure: recurring broker sync service.
- Why: prevents internal state from drifting from broker reality.
- Tools: Robinhood MCP, Alpaca API.
- Acceptance: mismatched position/order blocks new entries and alerts.
- Test: mocked broker open order and missing journal position.
- Rollback: disable new entries and manage positions manually.

Step 4: Add alerting.

- Build/configure: heartbeat file/endpoint plus external monitor.
- Why: silent failure is unacceptable for live automation.
- Tools: Better Stack, Sentry, or simple cron/email.
- Acceptance: alert fires on stale heartbeat, drawdown, broker failure, unreconciled position.
- Test: intentionally stop loop in paper mode.
- Rollback: local PowerShell monitor script.

Step 5: Add first paper anomaly lanes.

- Build/configure: relative-volume breakout/failure and announcement-aware reversal snapshots.
- Why: these fit current system and do not require expensive data first.
- Tools: scanner, event flags, Alpaca paper.
- Acceptance: 100+ labeled paper/counterfactual samples.
- Test: deterministic feature snapshots from fixture data.
- Rollback: disable strategy ids in registry.

## 12. Testing and Validation Plan

Unit tests:

- Risk limits.
- Position sizing.
- Readiness gates.
- Ticket normalization.
- Duplicate order guard.
- Secrets redaction.

Integration tests:

- Scanner to risk to intent.
- Intent to broker review.
- Broker review to paper order.
- Broker reconciliation.
- Alert generation.

Backtesting:

- No look-ahead.
- Corporate action adjusted prices.
- Point-in-time events.
- Conservative slippage/spread.
- Delisting and gap handling where available.

Walk-forward:

- Train, validate, test by market period.
- Keep final holdout untouched.
- Reject strategies that only work in one regime.

Paper trading:

- Minimum 20 distinct market days.
- Minimum 100 closed paper trades per strategy before Stage 4 consideration.
- Include no-trade and rejected setups.

Stress testing:

- Market crash day replay.
- Gap through stop.
- Broker API timeout.
- Data provider stale candles.
- Duplicate signal burst.
- Partial fill.
- Stop rejected.
- Network outage.
- Restart during open position.

Security testing:

- Confirm secrets never print.
- Confirm `.env` ignored.
- Confirm broker permissions.
- Confirm alert destination access control.

## 13. Deployment Plan

Environments:

- Development: local repo, mocked broker/data, unit tests.
- Staging: local or Render scan/risk app with fake broker and paper data.
- Paper trading: Alpaca paper endpoint, no live broker credentials needed.
- Limited live: Robinhood equity only, human approval, tiny notional.
- Full live: delayed until 90-day clean record and external monitoring.

Deployment checklist:

- Tests pass.
- Readiness gates loaded.
- Secrets present only in runtime environment.
- Broker account and endpoint verified.
- Paper/live endpoint mismatch check passes.
- Kill switch tested.
- Alerts tested.
- Rollback command documented.

Go/no-go:

- Go only if broker state reconciles, market data fresh, alerts green, and limits loaded.
- No-go on stale data, unknown broker positions, missing stop, failing tests, or disabled alerting.

## 14. Autonomous Trading Enablement Plan

Stage 0: Manual only

- Entry: default system state.
- Allowed: research, manual review, journaling.
- Risk limits: no automated orders.
- Monitoring: none required beyond logs.
- Exit: scanner and journal stable.
- Failure: any live automation path enabled accidentally.
- Human involvement: full.

Stage 1: Signal generation only

- Entry: scanner and evidence packets working.
- Allowed: generate candidates and risk reviews.
- Risk limits: no orders.
- Monitoring: data freshness.
- Exit: signals logged consistently.
- Failure: unreviewed execution.
- Human involvement: full.

Stage 2: Paper trading automation

- Entry: Alpaca paper credentials valid.
- Allowed: paper orders and counterfactual trials.
- Risk limits: paper exposure caps and strategy tags.
- Monitoring: paper fills, stale data, errors.
- Exit: 100+ closed samples and 20+ market days.
- Failure: paper/live endpoint mismatch or missing ledger.
- Human involvement: review outcomes, not every trade.

Stage 3: Human-approved live trades

- Entry: broker review/place tools proven, journal-first flow, explicit authorization.
- Allowed: tiny live equities with human approval.
- Risk limits: $10 starting notional, $5 daily loss, 1-2 open positions.
- Monitoring: broker state and protective stops.
- Exit: clean execution record and reconciliation.
- Failure: rejected orders, missing stops, unreconciled state.
- Human involvement: approve every live entry.

Stage 4: Limited autonomous live trades

- Entry: all readiness gates pass.
- Allowed: promoted equity strategies only.
- Risk limits: 0.5% risk/trade, 2% daily loss, 5% weekly loss, 2 open positions.
- Monitoring: external alerts required.
- Exit: 30-90 day clean record.
- Failure: drawdown, stale data, broker mismatch, alert outage.
- Human involvement: daily review and emergency override.

Stage 5: Full autonomous trading with strict risk caps

- Entry: 90-day clean record, monitoring, monthly model review, durable storage.
- Allowed: only promoted strategies and brokers.
- Risk limits: portfolio caps, strategy allocations, kill switches.
- Monitoring: 24/7 critical alerting.
- Exit: ongoing.
- Failure: any breach triggers downgrade to Stage 3 or Stage 2.
- Human involvement: oversight, incident response, promotion approval.

## 15. Final Recommendation

Implement immediately:

- Readiness gates in code.
- Paper lifecycle ledger.
- Broker reconciliation.
- External alerting.
- Secrets rotation.
- Emergency kill switch.
- Alpaca paper runner.
- Reversal and RVOL breakout/failure paper lanes.

Delay:

- Full autonomous live trading.
- Live options.
- Live crypto.
- Expensive direct exchange feeds.
- Deep order-book strategies.
- Any strategy requiring sub-second execution.

Unsafe now:

- Unlimited live AI-directed trading.
- Autonomous options trading.
- Autonomous crypto trading.
- Live scaling based on unvalidated paper results.
- Trading on LLM news summaries without deterministic data/event checks.

Top 10 highest-impact actions:

1. Rotate exposed Alpaca keys and use uncommitted runtime secrets.
2. Enforce `config/autonomous_readiness_gates.json` before every live order.
3. Add paper lifecycle ledger with closed-trade outcomes.
4. Add broker reconciliation loop.
5. Add heartbeat and external alerting.
6. Add kill switch and restart recovery protocol.
7. Keep Robinhood live lane at Stage 3 until gates pass.
8. Run Alpaca paper aggressively under Stage 2.
9. Add event flags to avoid fading real news.
10. Delay paid premium data until the paper lanes prove they need it.

