# Trading Monster Audit - 2026-06-16

## Diagnosis

This package is still primarily a review-only Living Screener MCP plus a separate local broker bridge in `tools/stock_bridge_loop.py`. The MCP has useful scan, risk, paper, journal, and proof-gate services, but it is intentionally not an order executor. Live order placement belongs in a separate broker bridge or host MCP.

The workspace is cluttered with many timestamped package folders and zips. Treat `living-screener-mcp-full-crypto-universe-20260615-0048-alpaca-options-router` as the current working candidate and archive older snapshots outside the active repo root before deployment.

The current autonomous bridge cycle is equity-first. Alpaca has low-level stock, option, and crypto order routing methods, but the autonomous selection and position-management loop still builds and manages only long equity entries. Options and crypto are not yet first-class autonomous lanes.

## Paper Trading Review

The latest package has empty CSV ledgers for `trade_ledger.csv` and `postmortems.csv`. SQLite contains scan, readiness, broker-proof, execution-control, and learning events, but not a clean population of paper trade opens/closes with full lifecycle P/L.

Observed event evidence:

- Repeated `MARKET_DATA_BLOCKED` and `AUTONOMOUS_DATA_BLOCKED` events.
- Three `review_outcome` events were `OUTCOME_UNAVAILABLE` because ticker/entry reference was missing.
- Learning samples are very small. The recurring proposal is `tighten_spread_penalty` from a low-confidence sample showing wide-spread options with poor follow-through.
- Robinhood equity route readiness was logged, Robinhood options route was blocked until active options MCP tools or another executor are available.

Conclusion: paper trading has not produced enough reliable closed-trade evidence to rank strategies confidently. The immediate lesson is process quality: improve market data, journal every paper open/close, and keep noisy exploration separate from cash gates.

## Broker Status

Robinhood:

- Current Codex connector read proof found an active Agentic cash account ending in 6199 with `agentic_allowed=true`, options level 2, about 99.62 USD buying power, and no reported holdings.
- Follow-up tool discovery exposed Robinhood equity review/place/cancel tools. Equity review was validated with a deliberately unmarketable BAC limit preview and returned a broker warning plus live quote data. No order was placed.
- This Codex session still did not expose Robinhood options order tools or crypto order tools.
- Public Robinhood docs list equity tools and rolling options tools for Agentic Trading, but say options are still rolling out. No official Robinhood Agentic crypto order tools were visible in the documented trading tool list.

Alpaca:

- No Alpaca credentials are stored in code, docs, or `.env`.
- The first user-supplied keys validated against Alpaca's live endpoint, not the paper endpoint. No order was placed.
- A later user-supplied paper key pair validated against `https://paper-api.alpaca.markets` on 2026-06-16. The paper account is active with 100,000 USD paper equity, options level 3, crypto status active, active crypto assets, and an options-contract probe. No order was placed.
- Alpaca docs support using the same Orders API endpoint for equities, crypto, and option contracts, with asset-specific validations.
- The bridge now validates Alpaca crypto more safely: crypto execution is disabled by default, market crypto orders are disabled by default, crypto orders must use either notional or qty, and limit-style crypto orders require `limit_price`.

## Code Changes Made

- Added Robinhood capability reporting in `tools/stock_bridge_loop.py`.
- Added explicit optional Robinhood options/crypto route methods that fail closed when tools are not exposed.
- Added stricter Alpaca crypto validation and `ALLOW_MARKET_CRYPTO=false`.
- Added tests for Robinhood missing options/crypto capabilities and Alpaca crypto safety checks.
- Normalized Alpaca Trading API base URLs so either `https://paper-api.alpaca.markets` or `https://paper-api.alpaca.markets/v2` works.
- Changed the Alpaca bridge startup script default from live Alpaca to paper Alpaca.
- Updated `.env.example` with `ALLOW_MARKET_CRYPTO=false`.

## EDGAR Recommendation

Use EDGAR as a swing/watchlist confidence layer, not a fast scalp signal.

Too delayed for the current fast style:

- 13F institutional holdings. They arrive too late for intraday/scalp use and mostly help slow watchlist research.
- Most S-1 and periodic-report signals. Useful for context, not timing.
- Generic 8-K parsing without event classification. Too noisy unless filtered by item type and price/volume response.

Potentially useful:

- Form 4 insider open-market buys, especially cluster buying, executive/CFO/CEO purchases, and buying after large selloffs. Use as a swing/watchlist boost, not an immediate buy trigger.
- 13D/13G activist or large-holder filings. Useful for watchlist generation and multi-day swing setups.
- 8-K material events if classified into high-signal categories and confirmed by technical/liquidity filters.
- Unusual ownership changes as a confidence booster beside technical setups.

Ignore or heavily down-rank:

- Planned insider sales, routine option exercises, tax-withholding transactions, tiny purchases, old 13F deltas, and filings without liquidity/tradability confirmation.

Automation path:

- Start with SEC `data.sec.gov` submissions JSON and company-ticker mapping for no-key ingestion.
- Add a thin `edgar_signal_service` that emits normalized events: `ticker`, `form_type`, `filed_at`, `signal_type`, `direction`, `confidence`, `freshness_hours`, `source_url`, and `reasons`.
- Keep EDGAR outputs out of execution gates at first. Feed them into watchlist generation, scan scorecard context, and post-trade analysis.
- Only promote EDGAR to a cash gate after backtests show additive value.

## Next Actions

1. Add Alpaca paper API credentials locally using environment variables, not code, then run the paper bridge.
2. Reconnect Robinhood Trading MCP and verify whether order tools are exposed in the active session.
3. Do not enable live mode until broker order review/place/cancel, open orders, positions, buying power, kill switch, and journal logging are all machine-proven.
4. Fix paper telemetry: every paper entry must have entry timestamp, symbol, asset class, strategy, signal snapshot, entry price, stop, target, exit reason, exit price, fees/slippage estimate, and P/L.
5. Build first-class broker lane interfaces for equity, options, and crypto before expanding autonomous selection beyond long equities.
6. Add EDGAR as a watchlist/confidence module only after the paper telemetry is clean.
