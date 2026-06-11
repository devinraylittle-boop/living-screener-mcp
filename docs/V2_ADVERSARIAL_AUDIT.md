# Living Screener MCP V2.0 Adversarial Audit

Build reviewed: `2026.06.11-paper-exploration-v2`

## 1. Executive Summary

Overall grade: **B- for safety, C for predictive accuracy, D+ for proof quality, not ready for real-money options use.**

The system is strongest where most trading agents are weakest: it is review-only, refuses broker execution, preserves PASS-first behavior, separates scan, options review, broker snapshot validation, paper/manual logging, learning labels, and rule proposals. Those boundaries should not be weakened.

The system is weakest where real trading accuracy lives: point-in-time data truth, options quote truth, fillability, calibration, and out-of-sample validation. It can support **paper trading and live manual review rehearsal**. It should not support real-money options decisions until the options truth layer is proven through MarketData/Tradier or a fresh broker-visible snapshot process, and until backtest/live paper evidence shows positive expectancy after spread and timing penalties.

Current readiness:

| Use case | Readiness | Reason |
| --- | --- | --- |
| Research and scans | Ready | Review-only, evidence packets, data flags, setup memory. |
| Paper/manual option journaling | Ready | Ledger, watch, close, outcome labels. |
| Live manual review | Conditional | Needs fresh broker snapshot and strict operator discipline. |
| Real-money manual options | Not ready | OPRA-grade truth/fillability/calibration not proven. |
| Automated broker trading | Block permanently for now | Outside current safety design. |

## 2. Top 20 Weaknesses

1. **No true point-in-time replay engine.** Current `BacktestService` is a rolling yfinance candle audit, not a full historical decision simulator with frozen market/option snapshots.
2. **Options truth gap remains unless MarketData/Tradier or broker snapshot is configured.** The new provider layer correctly exposes this, but automated truth is not present by default.
3. **No broker read-only reconciliation.** Manual action logs depend on human input, not broker-side position/order truth.
4. **Fillability assumptions are not proven.** Spread, bid/ask size, and quote age are checked, but historical fills are not modeled from real NBBO/OPRA.
5. **Outcome labels can mix signal quality and execution quality.** V2 records help, but future reports must aggregate signal outcome separately from execution outcome.
6. **Backtest selection bias.** Recent ticker lists are hand-picked movers/watchlist names, which can inflate confidence.
7. **Multiple-testing bias.** Many thresholds have been tried; improvements need holdout and walk-forward proof.
8. **Regime blindness.** Current scans know trend/VWAP/RVOL, but regime separation is shallow.
9. **Sector-relative strength is still missing.** SPY-relative strength exists; sector confirmation remains planned.
10. **Catalyst/news gap.** Earnings, FDA, lawsuits, analyst events, macro data, and halts are mostly manual or missing.
11. **Market open instability.** Tools acknowledge it, but the model does not fully learn opening-spread behavior by minute bucket.
12. **Power-hour instability.** No dedicated close-window penalty/calibration yet.
13. **Confidence miscalibration.** “Low-medium” and priority scores are not yet mapped to empirical win/expectancy buckets.
14. **Setup memory contamination risk.** Similarity can learn from weak outcomes if labels are noisy or manually entered late.
15. **PASS quality is undermeasured.** The system logs PASS, but needs formal false-negative and good-pass rates.
16. **Small-account caps are static.** A $1 cap is useful, but cap quality should depend on account size, spread, DTE, liquidity, and expectancy.
17. **No official OCC/OSI contract resolver.** Contract mismatch checks exist, but adjusted/non-standard contracts need stronger identity validation.
18. **Manual operator error remains high.** Manual snapshot form helps, but screenshots/receipts/checksums should be mandatory for real-money review.
19. **Release governance is good but incomplete.** Tests pass, but there is no shadow release comparison before promotion.
20. **No calibrated abstention score.** PASS is encouraged, but the system should quantify abstention confidence.

## 3. Top 20 Upgrades

1. Build `backtest_replay_engine` with frozen decision snapshots.
2. Add `generate_calibration_report`.
3. Add `generate_drift_report`.
4. Add `check_market_data_health` with provider, freshness, gaps, and timestamp lineage.
5. Add `compute_liquidity_gate` as a standalone reusable gate.
6. Add `resolve_occ_contract` or OSI parser/validator.
7. Add `record_manual_execution_receipt`.
8. Add `reconcile_broker_activity_read_only` when a safe broker read-only tool exists.
9. Add `shadow_release_review`.
10. Add `rule_registry` with active, proposed, shadow, rejected, rollback states.
11. Add sector-relative strength.
12. Add market-regime classifier.
13. Add time-of-day performance buckets.
14. Add spread/fillability outcome buckets.
15. Add false-positive analyzer.
16. Add false-negative analyzer.
17. Add setup-quality analyzer.
18. Add event/catalyst flags.
19. Add paper/manual trade receipt hashes.
20. Add premarket/opening/afternoon/close playbooks with separate thresholds.

## 4. Backtest Plan

The current backtest should be treated as a rough signal audit only. V2 needs a real replay engine:

Data required:

- Intraday candles available at each timestamp only.
- Quote snapshots with source, receipt timestamp, and quote age.
- Options chain snapshots with bid, ask, bid size, ask size, volume, OI, IV, expiration, strike, contract symbol, quote timestamp.
- SPY and sector ETF candles at the same timestamp.
- Corporate action and adjusted contract flags.
- Earnings/news/event calendar.
- Market regime labels.

Method:

1. Freeze every decision timestamp.
2. Build only the features available at that timestamp.
3. Run the exact active rule version.
4. Save every `CANDIDATE`, `WATCH_ONLY`, and `PASS`.
5. If options review is reached, use the historical option snapshot closest to but not after the decision timestamp.
6. Grade outcomes at 5m, 10m, 15m, 30m, 60m, close, and custom max-hold.
7. Compute MFE, MAE, time-to-MFE, time-to-MAE, VWAP reclaim/reject, spread drift, and liquidity decay.
8. Separate signal P/L proxy from execution P/L proxy.

Leakage controls:

- No future volume.
- No future candle high/low in signal features.
- No future option volume/OI unless timestamped and known at decision time.
- No future news.
- No survivor-only ticker universe.
- No using the later “best contract” if it was not acceptable at the timestamp.

Success metrics:

- Expectancy after spread/slippage penalty.
- Precision by confidence bucket.
- False-positive rate.
- False-negative rate.
- Good-pass rate.
- Abstention quality.
- Drawdown proxy.
- Setup decay speed.
- Contract fillability score.
- Performance by time of day, ticker, sector, market regime, and DTE.

## 5. Strategy Diagnosis

Current effective strategy: **hybrid intraday momentum/relative-strength scalp scanner with options suitability filtering and small-account friction penalties.**

What it gets right:

- Requires stock setup before options review.
- Keeps options and small-account gates separate.
- Penalizes wide spreads, 1DTE, high max loss, VWAP conflict, and weak liquidity.
- Defaults to PASS.
- Logs outcomes and learning proposals without auto-applying them.

Where it is confused:

- It mixes momentum, VWAP trend-following, relative strength, and cheap-option selection without calibrated weights.
- RVOL is a warning, not a hard gate, but priority scoring still treats it inconsistently across contexts.
- A cheap contract can outrank a better setup if small-account sizing dominates too much.
- The strategy does not yet know when a move is already exhausted.

V2 strategy should become:

**Abstention-heavy directional momentum continuation with regime/sector confirmation, broker/OPRA-grade options truth, friction-adjusted contract selection, and calibrated confidence.**

## 6. Profitability Plan

Do not chase more trades. Improve expectancy:

- Trade fewer names, not more.
- Require clean stock setup, direction, VWAP, sector/index alignment, and options tradability.
- Prefer 2-5 DTE for small-account scalps unless 1DTE is exceptional.
- Penalize spreads and cheap-contract tick risk.
- Model time decay explicitly.
- Avoid open noise until spreads stabilize.
- Reject candidates where the option contract is good but the stock setup degraded.
- Reject candidates where the stock setup is good but the option chain is poor.
- Track missed moves to avoid becoming too restrictive.
- Use paper/manual live evidence before loosening any rule.

## 7. Accuracy Improvement Loop

Daily loop:

1. Run market readiness.
2. Run market-open observer.
3. Run live review cycle.
4. Log every candidate, watch-only, and meaningful PASS.
5. If reviewed manually, validate broker snapshot.
6. If paper/manual entry occurs, record exact fill, quote, snapshot, and receipt.
7. Check outcome at fixed horizons.
8. Classify: false positive, good signal, missed move, good pass, early move then fade, bad contract, stale data.
9. Summarize by setup fingerprint.
10. Generate rule proposals.
11. Shadow-test proposals.
12. Backtest out of sample.
13. Human approves or rejects.
14. Register rule version.
15. Keep rollback path.

Never auto-apply learning proposals.

## 8. Endpoint, Tool, And Schema Changes

Existing tools to tighten:

- `run_scalp_scan`: add `market_regime`, `sector_context`, `time_bucket`, `calibrated_confidence`, `abstention_confidence`.
- `review_candidate_for_options`: include `real_money_options_truth_gate`, `contract_selection_reason`, `why_not_selected`.
- `validate_broker_option_snapshot`: require quote timestamp for real-money readiness; support screenshot/receipt hash.
- `manual trade desk`: require a decision record id and broker snapshot id.
- `manual snapshot form`: add explicit stale warning if quote timestamp is missing.
- `paper options ledger`: separate signal result from execution result in summary buckets.
- `session risk guard`: add active paper/manual exposure by contract and underlying.
- `market readiness`: add provider health and market calendar awareness.
- `market open observer`: track opening minute bucket and spread stabilization.
- `live review cycle`: rank only if stock, option, truth, liquidity, and risk gates all pass.
- `learning dashboard`: add confidence bucket, setup fingerprint, and rule-version aggregates.
- `evidence packets`: freeze rule version, provider versions, and timestamp lineage.
- `setup memory`: weight only clean labeled outcomes; quarantine ambiguous labels.
- `failure-mode audit`: convert gaps into actionable checklist status.

New tools:

- `check_market_data_health`
- `compute_liquidity_gate`
- `resolve_occ_contract`
- `record_manual_execution_receipt`
- `reconcile_broker_activity_read_only`
- `generate_calibration_report`
- `generate_drift_report`
- `shadow_release_review`
- `rule_registry`
- `backtest_replay_engine`
- `setup_quality_analyzer`
- `false_positive_analyzer`
- `false_negative_analyzer`

## 9. V2.0 Architecture

Layers:

1. **Data truth layer:** quote/candle/option timestamp lineage, provider health, stale/missing/malformed flags.
2. **Market readiness layer:** market calendar, time bucket, spread stabilization, regime.
3. **Equity setup layer:** trend, VWAP, RVOL, relative strength, sector/index, catalyst, higher timeframe.
4. **Options truth layer:** MarketData/Tradier or broker snapshot, quote age, OCC identity, adjusted-contract block.
5. **Liquidity/fillability layer:** bid/ask width, absolute spread, bid/ask size, volume, OI, expected slippage.
6. **Broker-visible validation layer:** manual or read-only broker confirmation.
7. **Human decision layer:** checklist, approval phrase, limit-only discipline.
8. **Paper/manual ledger layer:** entry/exit receipts, fill/reference drift.
9. **Outcome labeling layer:** signal vs execution labels, fixed horizons.
10. **Learning/proposal layer:** proposals only, no auto-apply.
11. **Governance/release layer:** rule registry, shadow releases, rollback.
12. **Dashboard/observability layer:** health, calibration, drift, decisions, misses, risk.

## 10. Permanently Blocked Until Proven

- Approving stale quotes.
- Approving wide spreads without exceptional evidence and broker snapshot.
- Using yfinance/non-OPRA options data as real-money truth without broker-visible validation.
- Relaxing small-account caps because of impatience.
- Approving adjusted contracts without OCC/OSI validation.
- Applying learned rules without out-of-sample tests.
- Increasing trade frequency without improving precision.
- Any automated broker action.
- Treating broker-order simulation as real execution evidence.
- Trading from stock setup alone.
- Trading from options-chain quality alone.
- Trading after stock setup degraded.
- Treating missing quote timestamps as fresh.
- Treating screenshots without timestamp as proof.

## 11. Prioritized Roadmap

Immediate fixes:

1. Add `check_market_data_health`.
2. Add `compute_liquidity_gate`.
3. Add calibration report for existing outcomes.
4. Add false-positive/false-negative analyzers.
5. Tighten manual snapshot timestamp requirements.

Pre-real-money requirements:

1. MarketData/Tradier or equivalent options truth.
2. Broker-visible snapshot receipt process.
3. Point-in-time replay engine.
4. Out-of-sample and walk-forward tests.
5. Rule registry and rollback.
6. Live paper/manual evidence with positive expectancy.

V2.0 launch requirements:

1. Calibration by confidence bucket.
2. Regime-separated thresholds.
3. Sector-relative strength.
4. Drift reports.
5. Shadow release review.

Later enhancements:

1. Catalyst/news feed.
2. L2/order-flow proxy.
3. Better contract optimizer.
4. Portfolio exposure model.

Avoid for now:

- Automated execution.
- 0DTE expansion.
- More aggressive trade frequency.
- Complex multi-leg strategies.
- Loosening filters from one-day samples.

## 12. Final Recommendation

Build next: **point-in-time replay and calibration.**

Do not build next: automated broker trading, looser entry gates, 0DTE expansion, or anything that increases frequency before precision is proven.

Tighten/block: stale quote handling, real-money options truth, manual snapshot timestamps, adjusted contracts, learned-rule promotion, and PASS outcome measurement.

What would make the system powerful: it must know not only why a setup passed, but whether similar setups actually worked under the same regime, spread, DTE, time bucket, and contract liquidity conditions.

Evidence required before real-money manual use:

- 100+ point-in-time candidate samples across regimes.
- Positive expectancy after spread/slippage penalties.
- Calibrated confidence buckets.
- PASS false-negative rate understood.
- At least several live paper/manual sessions logged with receipts.
- Broker snapshot or automated options truth available.
- No release mismatch.
- No safety regression.



