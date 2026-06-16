# Capability Audit

Audit date: 2026-06-16

## Scope

This audit inspected the local trading-bot package without assuming advertised capabilities were wired into the active execution path. The goal was to identify what the codebase can actually do, what is underused, and where safe measurable optimization can improve paper trading and research without weakening real-money controls.

## High-Level Finding

The package has a broad review/research intelligence layer and a deliberately narrow execution layer. That is the right shape for a small-account autonomous trading system at this stage: scans, evidence, learning, paper exploration, and launch-decision tooling are available, while live-cash autonomy remains blocked by explicit readiness gates.

The largest underuse found is not missing capability; it is integration. Scanner rows already include evidence scorecards, data-confidence signals, SPY-relative strength, and data flags, but the stock bridge candidate selector was primarily ranking by stock score and relative volume, then filtering by VWAP, tradability, and spread. That means the running Alpaca paper lane could ignore useful evidence already computed upstream.

## Confirmed Capabilities

### Market Scanning And Review

- `run_market_scan`, `run_scalp_scan`, `run_broad_opportunity_scan`, and related fallback endpoints expose equity scanning.
- Scanner output includes:
  - stock score
  - direction and setup quality
  - relative volume
  - VWAP state
  - quote/candle validity context
  - SPY-relative strength diagnostics
  - evidence scorecard modules
  - evidence packet with data confidence and data flags
- Debug/schema endpoints document expected scan payload structure, including evidence packet fields.

### Options Review

- `review_candidate_for_options` combines stock setup review with options-chain checks.
- Options service supports manual, yfinance preliminary, MarketData, and Tradier provider paths.
- The options gate distinguishes chain acceptability from small-account suitability.
- Market options are disabled by default through execution-router policy.

### Paper And Learning Systems

- Paper exploration tools exist:
  - `run_paper_exploration`
  - `run_paper_exploration_followup`
  - `summarize_paper_exploration`
- Paper exploration is explicitly noisy and tagged so weak setups can be studied without changing cash gates.
- Learning tools classify outcomes and generate rule-change proposals marked `do_not_auto_apply`.
- Setup memory can compare a candidate with past reviews and lessons.

### Backtesting And Simulation

- `BacktestService` performs a rolling candle audit with no-lookahead notes, horizon summaries, win rate, expectancy, MFE, and MAE.
- Crypto paper backtesting supports strict, balanced, and exploratory profiles over the Robinhood crypto universe.
- Backtest outputs are research signals, not live approvals.

### Crypto Research

- Crypto universe and crypto paper services are present.
- Crypto live-test gate exists as a validation/reporting gate.
- Exchange execution remains intentionally unavailable unless separate adapter proof is added.

### Control Plane And Safety

- Strategy registry, shared intelligence layer, data truth cockpit, launch decision, proof bridge, session risk guard, and trading dashboard tools exist.
- `config/autonomous_readiness_gates.json` keeps `global_live_default=false`.
- Stage 2 Alpaca paper automation is allowed.
- Stage 4/5 autonomous live-cash trading is blocked.
- Stage 3 live bridge still requires human-approved operation.

### Broker Bridge

- `tools/stock_bridge_loop.py` can run a local stock bridge.
- It supports Robinhood MCP and Alpaca routing.
- Alpaca paper endpoint handling is present and journals paper as not real cash.
- Risk controls include max notional, max open positions, max trades/day, daily loss halt, stop-loss/take-profit position management, broker checks, spread cap, and open-order capacity checks.

## Underused Assets

1. Evidence scorecard is present in scan output but was not used by the paper bridge selector.
2. Evidence/data confidence is present but was not used by the paper bridge selector.
3. Relative strength versus SPY is present but was only diagnostic upstream.
4. Data flags such as stale quote, missing relative strength, or low confidence were not represented in bridge ranking diagnostics.
5. Shared intelligence, setup memory, and learning signals are available but not yet connected to active paper bridge ranking.
6. Backtest service lacks trading-cost metrics such as slippage/spread/fees and richer risk-adjusted metrics.
7. Paper exploration exists but appears exposed primarily through MCP/endpoints, not as a background worker tied to the local Alpaca paper process.

## Active Safety Limits

- This MCP package cannot place orders directly.
- Local bridge execution is separate from the hosted MCP.
- Full autonomous live-cash trading is blocked by readiness gates.
- Alpaca paper automation is the only autonomous submission mode currently appropriate.
- Live endpoint use with Stage 2 remains refused.
- Options/crypto market orders remain disabled by default.

## Primary Gap To Fix First

The running paper bridge should use more of the scanner's existing intelligence before deciding which symbol to paper trade. This is measurable through unit tests and logs, and it improves data gathering quality without touching live-cash autonomy.

