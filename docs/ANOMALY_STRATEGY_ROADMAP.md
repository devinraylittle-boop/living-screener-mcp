# Anomaly Strategy Roadmap

## Research Takeaway

The best near-term path is not a black-box chart bot. It is a layered anomaly program that uses paper trading and shadow testing to separate durable, cost-resistant edges from noisy setups.

The strongest practical families for a small account are:

1. Earnings drift with text and attention features.
2. Announcement-aware reversals that avoid earnings and true-news repricing.
3. Sector-filtered medium-term momentum.
4. Relative-volume breakout and failure models in liquid names.
5. Overnight momentum baskets after open/close execution costs are modeled.

Options-led signals, ETF-flow dislocations, and retail-attention bursts stay later-stage until the data stack and slippage models are strong enough.

## Implementation Order

### Phase 1: Paper-First Intraday Models

Start with relative-volume breakout/failure and announcement-aware reversal because they fit the current scanner and Alpaca paper setup.

Required additions:

- Event flags for earnings, known catalysts, and broad macro windows.
- Intraday feature snapshots: RVOL, VWAP deviation, spread estimate, ATR percentile, sector confirmation, residual return.
- Paper ledger rows for rejected, avoided, continued, and reversed variants.
- Outcome worker for 30-minute, end-of-day, 1-day, and 3-day follow-up.

Live-cash impact: none until promotion gates are met.

### Phase 2: Regime Layer

Add volatility and breadth state as strategy selectors rather than standalone alpha.

Required additions:

- Realized volatility percentile.
- ATR percentile.
- Breadth and sector dispersion.
- Market stress flags.
- Rule that shrinks or disables live sizing when volatility-of-volatility rises.

Live-cash impact: risk adjustment only.

### Phase 3: PEAD And Text

Build a slower event lane for earnings drift.

Required additions:

- Point-in-time earnings calendar.
- Exact announcement timestamps.
- Press-release and call-transcript text ingestion.
- Numeric surprise proxy.
- Text surprise or tone-change score.

Live-cash impact: shadow only until point-in-time timestamp quality is proven.

### Phase 4: Options And Flow

After Tradier or another options data source is connected, use options as a signal layer first and an execution lane second.

Required additions:

- Chain quality scoring.
- Quote age and spread model.
- IV, skew, volume, open interest, and call/put imbalance.
- Options-led stock score.
- Strict event-risk filter.

Live-cash impact: no options cash orders until broker tools, chain quality, and paper fills are proven.

## Strategy Registry

The machine-readable strategy list is in `config/anomaly_strategy_registry.json`.

Current default policy:

- Paper enabled.
- Cash live disabled.
- Manual promotion required.
- Cost model required.
- Out-of-sample validation required.

Promotion gate:

- At least 50 closed paper trades.
- At least 15 distinct market days.
- Profit factor after costs of at least 1.2.
- Strategy drawdown below 8%.
- Slippage, gap-risk, and kill-switch checks present.

## Live-Cash Rule

No anomaly is allowed to weaken the live-cash gate. A signal may increase attention, trigger paper exploration, or improve candidate ranking, but it cannot bypass:

- Broker review.
- Quote freshness.
- Spread limits.
- Position limits.
- Daily loss limits.
- Open-order checks.
- Journal-first logging.

