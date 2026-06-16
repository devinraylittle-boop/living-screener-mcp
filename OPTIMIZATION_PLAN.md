# Optimization Plan

Audit date: 2026-06-16

## Objective

Improve the autonomous paper-trading package by making the active stock bridge consume more of the intelligence already produced by the scanner, while preserving all real-money safety barriers.

## Current Best Optimization Target

The highest-impact safe target is the stock bridge candidate selector in `tools/stock_bridge_loop.py`.

Before this optimization, the selector ranked candidates mostly by:

- stock score
- relative volume

Then it filtered by:

- long direction
- valid setup quality
- minimum score
- minimum relative volume
- above VWAP
- tradability
- valid quote
- spread cap

That is safe, but it leaves useful upstream data unused. Scanner candidates already carry evidence scorecards, data-confidence metadata, relative-strength diagnostics, and data flags.

## Implementation Plan

1. Add evidence-aware candidate diagnostics to the stock bridge.
   - Extract scanner evidence scorecard score when available.
   - Extract evidence packet data-confidence score/label when available.
   - Extract SPY-relative strength label and excess trend when available.
   - Extract data flags from evidence packets.

2. Preserve existing hard gates.
   - Do not lower score, RVOL, VWAP, tradability, quote, spread, capacity, drawdown, or broker-check requirements.
   - Do not enable live-cash autonomy.
   - Do not auto-apply learning rules.

3. Rank candidates with a transparent composite score.
   - Base score remains the scanner's `stock_score`.
   - Evidence score and data confidence add modest support.
   - Leading SPY adds support.
   - Lagging SPY, stale data, and low confidence add penalties.

4. Log top candidate diagnostics.
   - Log why the selected candidate ranked first.
   - Log top rejected/ranked candidates with score components and rejection reasons.
   - Keep logs secret-free.

5. Add tests.
   - Strong evidence should outrank a similar higher raw-score candidate with weak evidence.
   - Stale/low-confidence candidates should be rejected or downgraded with explainable reasons.
   - Existing hard gates should still prevent invalid candidates.

6. Validate.
   - Run targeted unit tests for the bridge selector.
   - Run existing stage-gate and Alpaca router tests.
   - If time allows, run the full suite.

## Next Safe Improvements After This Patch

1. Add cost-aware backtest metrics.
   - Spread/fee/slippage assumptions.
   - Profit factor after costs.
   - Max drawdown and average adverse excursion thresholds.

2. Add paper-bridge outcome follow-up.
   - Reconcile paper orders/fills with scanner evidence at entry time.
   - Create daily paper-trade summaries grouped by score components.

3. Connect setup memory to paper ranking as advisory.
   - Penalize similar-risk-seen-before setups in paper selection.
   - Keep this diagnostic until backtested.

4. Add a background paper exploration scheduler.
   - Keep noisy exploration separate from the main paper bridge.
   - Tag all noisy trials as non-cash evidence.

5. Add sector-relative strength.
   - Scanner already marks sector-relative strength as planned.
   - This should be added as an evidence module before it affects ranking.

## Non-Goals

- No real-cash autonomous order placement.
- No removal of live readiness gates.
- No hardcoded secrets.
- No ticker-specific strategy shortcuts.
- No fabricated performance claims.

