# Living Screener MCP

Review-only hosted MCP for market scanning, trade planning, risk checks, journaling, and postmortems.

This app does **not** store Robinhood credentials, does **not** call Robinhood APIs, and cannot place brokerage orders. Robinhood Trading MCP stays separate for broker data, order review, and any future exact user-approved execution.

## Current Build

```text
2026.06.09-session-loop
```

## Render Environment

Keep your Finnhub key only in Render:

```text
FINNHUB_API_KEY=<your key>
```

The checked-in `render.yaml` defaults to:

```text
MARKET_DATA_PROVIDER=finnhub
MARKET_DATA_INTERVAL=5m
MARKET_DATA_PERIOD=5d
MAX_DATA_STALENESS_MINUTES=1440
REGULAR_MARKET_MAX_STALENESS_MINUTES=15
REVIEW_ONLY=true
PLACE_ORDERS=false
HOSTED_MODE=false
PENDING_BUY_RECHECK_SECONDS=60
SCALP_CANDIDATE_SCORE_THRESHOLD=65
SCALP_MAX_CONTRACT_PRICE=1.00
```

This blueprint uses Render's free web-service plan and does not attach a persistent disk. That keeps the first hosted version inexpensive, but local SQLite journal entries can disappear after Render sleeps, restarts, or redeploys the service. The scanner and safety checks still work normally.

Finnhub is used as the primary quote source. Finnhub's stock candle endpoint may require paid access, so this build safely falls back to yfinance for candles when Finnhub returns no candle data. Market-closed freshness handling accepts the latest regular-session close during overnight and weekend periods instead of rejecting it just because the market is closed.

Options trade plans are gated by separate options-chain validation. The MCP checks bid/ask spread, volume, open interest, expiration risk, and max loss before any review-only options plan can be produced. If those fields are missing or weak, the result is `NO_TRADE_PLAN`.

Use `review_candidate_for_options` when a stock candidate appears. It runs the stock setup review and the options-chain gate together so the result is either `NO_TRADE_PLAN` or `REVIEW_ONLY_OPTIONS_READY`.

Pending buy orders should be reconsidered after 60 seconds. Use `review_pending_buy_order` with the ticker, submitted timestamp, and limit price. It cannot cancel or replace anything; it returns whether the pending buy is still valid for review or needs reconsideration.

Use `run_scalp_scan` for a broader review-only moving-equities scan. It uses a larger liquid/options-friendly universe and scores absolute movement, recent momentum, relative volume, and VWAP alignment. This mode is wider, but it still only produces review candidates; options and pending-order gates remain separate.

Scalp reviews use score threshold `65` as the primary quality gate. Relative volume below `SCALP_MIN_RELATIVE_VOLUME` is reported as a caution/priority warning, not an automatic rejection, because backtests did not support RVOL 1.15 as a hard disqualifier. RVOL now reports a `relative_volume_status`; it prefers same-time-of-day volume comparison when available and returns `null` instead of pretending unavailable RVOL is truly `0.0`.

`review_candidate_for_options` also returns `small_account_review` for scalp mode. This is a review-ordering aid, not an execution signal. It lowers priority for 1DTE contracts, large max loss, wide spreads, and VWAP/direction conflicts. Any warning caps the priority below a perfect score so risky contracts do not rank as clean 100s. The final scalp gate now separates `OPTIONS_CHAIN_ACCEPTABLE` from `SMALL_ACCOUNT_SCALP_ACCEPTABLE`; an options chain can pass technically while still returning `NO_TRADE_PLAN` for small-account scalp use.

Small-account reviews now include a `friction_adjusted_score`, `friction_band`, and `friction_adjusted_review`. This score penalizes spread percentage, dollar spread, cheap-contract tick risk, weak volume/open interest, 1DTE decay, elevated max loss, and estimated round-trip slippage. If friction is too weak, the setup remains `NO_TRADE_PLAN` even when the chain technically has an acceptable contract.

Small-account scalp hard stops: 0DTE is blocked; 1DTE requires exceptional stock score, confirmed RVOL, tight spread, and VWAP alignment; max loss above the small-account cap is blocked; and direction/VWAP conflicts are blocked.

Scalp options reviews default to `SCALP_MAX_CONTRACT_PRICE=1.00` when no explicit `max_contract_price` is provided. This prevents high-priced contracts from being treated as small-account candidates. If no acceptable contract passes the options-chain gate, `small_account_review.priority_score` is `0`.

When yfinance rejects an options chain, results include `best_rejected_contracts` with exact rejection reasons and `closest_to_pass_reason`. If a broker screen shows a live contract that yfinance misses, use `validate_broker_option_snapshot` with manually supplied bid, ask, volume, open interest, DTE, strike, and contract symbol. This validates the broker-visible snapshot without storing credentials or placing orders.

If the quote endpoint fails but fresh candle data is available, the scanner can derive a quote from the latest candle close. The quote summary marks this with `derived_from_candles: true` and `previous_close_source: prior_candle_close`, so the model can continue reviewing without pretending it came from a live quote endpoint or prior-session close.

Review outcome memory starts with `log_review_decision`, then later `check_review_outcome`. Logged reviews include `review_timestamp`; outcome checks only compute 15m/30m/1h style horizon returns and max favorable/adverse excursion from candles at or after that timestamp. If no review timestamp is supplied, current return can still be checked, but horizon learning is marked unanchored and left unavailable. Use `summarize_review_outcomes` to aggregate supplied outcomes. These are learning tools only and cannot place broker orders.

The mistake engine turns those outcomes into research labels. Use `log_research_snapshot` to save a scan/review/pass snapshot, `classify_review_outcome` after an outcome check, `summarize_learning` to see which mistake types are recurring, and `generate_learning_rule_proposals` to produce evidence-backed rule-change hypotheses. These proposals are deliberately marked `do_not_auto_apply: true`; they must be backtested and manually accepted before any active gate changes.

Setup memory compares new review-only candidates against prior logged reviews and learning labels. Every options review now includes `setup_memory`, with a setup fingerprint, similarity summaries, and a `memory_signal` such as `NO_MEMORY_YET`, `SIMILAR_REVIEW_HISTORY_FOUND`, `SIMILAR_EDGE_SEEN_BEFORE`, or `SIMILAR_RISK_SEEN_BEFORE`. This is advisory context only; it cannot approve a trade or alter active gates by itself.

Market readiness and review harvest tools make the live-market workflow repeatable. Use `market_readiness_check` or `/ops/market-readiness` to verify data quality and whether stock candidates exist. Use `run_review_harvest` or `/ops/review-harvest` to run a scalp scan, options-review only valid directional stock candidates, rank only setups that pass `SMALL_ACCOUNT_SCALP_ACCEPTABLE`, and return follow-up outcome checks for 15m/30m/60m review. Harvest output is still review-only and cannot create, place, simulate, submit, modify, or cancel orders.

Session loop tools connect the workflow for live-market use. Use `get_market_session_playbook` or `/ops/session-playbook` before the session to get a timed operating checklist. After a harvest has produced ranked candidates, use `run_latest_harvest_followup` or `/ops/harvest-followup` to check outcomes from the latest harvest, summarize results, and classify lessons through the mistake engine. Follow-up labels remain research-only; rule proposals are not auto-applied.

Off-hours research tools keep the system productive when U.S. options liquidity is stale or closed. Use `get_offhours_research_plan` and `run_global_research_scan` for underlying-only studies across crypto and global instruments. These scans do not validate U.S. options chains and must not be treated as broker action. Use them to find patterns worth logging and checking later with the mistake engine.

The off-hours scanner treats unavailable volume as unknown instead of bearish. If high/low range data is unusable, it falls back to close-to-close movement expansion so crypto/global feeds can still be studied without pretending missing RVOL is truly weak.

The yfinance quote fallback now treats `previous_close` as the previous regular-session close when that can be inferred from recent minute data. It falls back to the prior minute only when no previous session is present.

Pre-move blueprint tools expose the research-backed scoring architecture without changing broker safety. Use `get_trading_monster_blueprint`, `get_feature_registry`, `get_scoring_model`, and `explain_premove_score` to inspect evidence modules, false-positive penalties, missing premium data, and the options-structure map. Scanner candidates now include `key_signals.evidence_scorecard` so every candidate can show what helped, what hurt, and what data is still missing.

Evidence packets harden the learning loop. Every scan row now includes a compact `evidence_packet` with provider lineage, quote/candle timestamps, freshness states, data-confidence flags, missing modules, and replay fields. Use `build_evidence_packet`, `build_evidence_packets_from_scan`, and `summarize_evidence_packets` to archive or summarize the exact evidence state before using outcomes for learning.

Debug validation routes let ChatGPT or a browser validate the live schema without running a real scan. Use `/health/full`, `/debug/tool-manifest`, and `/debug/scan-schema` to confirm build identity, required tool exposure, evidence packet shape, scorecard fields, known blindspots, and expected-build guards.

SPY-relative strength is now included as a diagnostic module in scan output. It compares each ticker's trend and recent trend against SPY, reports `key_signals.relative_strength`, and adds a `relative_strength_vs_spy` scorecard module. This is not a hard execution gate yet; sector-relative strength remains planned.

## Browser Fallback Endpoints

These routes call the same review-only services as the MCP tools. They exist so you can keep working even if ChatGPT's connector does not expose the MCP namespace in a given turn.

```text
GET /safety
GET /health/full?expected_build_version=2026.06.09-session-loop
GET /scan/scalp?tickers=AMZN,SOFI,SHOP,SMCI,HOOD,TSLA&max_candidates=25
GET /scan/market?mode=conservative_review_only&tickers=SPY,QQQ,KO,PG
GET /ops/session-playbook?tickers=AMZN,SOFI,SHOP,SMCI,HOOD,TSLA&account_value=50
GET /ops/session-playbook?tickers=AMZN,SOFI,SHOP,SMCI,HOOD,TSLA&format=html
GET /ops/market-readiness?tickers=AMZN,SOFI,SHOP,SMCI,HOOD,TSLA&max_candidates=25
GET /ops/review-harvest?tickers=AMZN,SOFI,SHOP,SMCI,HOOD,TSLA&max_candidates=25&review_top_n=8
GET /ops/review-harvest?tickers=AMZN,SOFI,SHOP,SMCI,HOOD,TSLA&format=html
GET /ops/harvest-followup?limit=5&classify=true
GET /ops/harvest-followup?limit=5&classify=true&format=html
GET /review/options?ticker=SMCI&direction=put&mode=scalp_review
GET /review/options?ticker=SOFI&direction=put&mode=scalp_review&max_contract_price=1.00
GET /review/options?ticker=SMCI&direction=put&mode=scalp_review&format=html
GET /review/options?ticker=SMCI&direction=put&mode=scalp_review&format=json
POST /review/broker-option-snapshot
POST /review/log-decision
GET /review/outcome?ticker=SMCI&direction=put&entry_reference=41.46&review_timestamp=2026-06-09T14:46:19Z
POST /review/outcome
POST /learning/classify
POST /learning/proposals
POST /learning/setup-memory
GET /learning/dashboard
GET /research/offhours
GET /research/global-scan?market=crypto&period=5d&interval=5m
GET /research/global-scan?market=global&period=5d&interval=5m&format=html
GET /research/blueprint
GET /research/features
GET /research/scoring-model
POST /research/explain-score
POST /research/evidence-packet
POST /research/evidence-packets-from-scan
GET /research/evidence-summary
POST /research/evidence-summary
GET /debug/tool-manifest
GET /debug/scan-schema?expected_build_version=2026.06.09-session-loop
GET /crypto/rules
GET /crypto/backtest?symbols=ETH-USD,SOL-USD&period=10d&interval=5m&profile=strict&exclude_symbols=BTC-USD,DOGE-USD
```

Opening `/review/options` in a normal browser returns a cleaner HTML view with status, gates, selected contract, warnings, rejected-contract diagnostics, and raw JSON. Add `format=json` when you want machine-readable output.

Opening `/learning/dashboard` in a normal browser shows recent learning labels, recurring mistake tags, and any rule proposals with enough evidence. It is a research dashboard only.

Opening `/research/global-scan` in a normal browser with `format=html` or an HTML accept header shows an off-hours research table with score, direction, relative volume, range expansion, compression-break status, and lesson tags. Opening `/crypto/backtest` gives a paper-only crypto backtest view.

Opening `/research/blueprint`, `/research/features`, or `/research/scoring-model` shows the Trading Monster research map in a readable format. These are planning and explanation pages only; they do not change active gates by themselves.

Opening `/scan/scalp` or `/scan/market` now returns compact evidence packets on each row. Use `/research/evidence-summary` to see recurring data-confidence problems such as missing catalyst context, missing relative strength, derived quotes, stale candles, or weak relative volume.

Opening `/ops/review-harvest` in a browser returns a ranked review-only harvest page. It is the fastest live workflow for tomorrow: scan, validate stock candidates, validate options chains, rank small-account acceptable setups, show warnings, and produce follow-up outcome checks.

Opening `/ops/session-playbook` returns a timed review-only operating checklist for pre-market checks, opening stabilization, harvest windows, afternoon decision review, and after-action learning. Opening `/ops/harvest-followup` grades the latest harvest's ranked candidates and sends the outcomes into the learning classifier when `classify=true`.

Opening `/debug/scan-schema` returns a static example candidate with `key_signals.evidence_scorecard`, `evidence_packet`, `missing_modules`, `penalty_reasons`, `confidence_band`, `known_blindspots`, and `why_not_ranked`. It does not call market data or create a trade plan.

Every fallback response includes:

```json
{
  "review_only": true,
  "can_place_order_from_this_mcp": false,
  "can_cancel_order_from_this_mcp": false
}
```

These endpoints do not place, cancel, modify, submit, or simulate broker orders.

Backtests now apply the scalp relative-volume gate when the engine name includes `scalp`, and return aggregate horizon summaries for 15m, 30m, 1h, and the configured close/forward window.

Crypto overnight work is paper-only. Use `start_crypto_paper_session` to log the intended session, `get_crypto_paper_rules` to inspect the rules, and `run_crypto_paper_backtest` to simulate long-only crypto scalps over recent yfinance candles. These tools do not run a background worker, do not call Robinhood, and cannot place or cancel orders.

If the ChatGPT connector cannot see the crypto-specific tools, call the already-visible `run_backtest` tool with `engine="crypto-paper-overnight"`. This build routes that engine name to the same crypto paper simulator and returns paper-only results.

The crypto paper model now adds entry discipline after early tests showed late-spike exhaustion. Long entries require a broader uptrend, a controlled reclaim, and relative-volume support. The model skips high-volume candles that are already extended from recent price, uses breakeven-fade exits after early favorable movement, and returns aggregate paper stats including total trade count, aggregate return, full win rate, stop-loss frequency, max drawdown, exit-reason counts, and `PASS`/`PAPER_WATCH` verdict.

Use `config_overrides.profile` with `run_backtest(engine="crypto-paper-overnight")` to compare rule strictness without adding new MCP tools. Available profiles are `strict` default, `balanced`, and `exploratory`. `balanced` slightly loosens relative-volume/reclaim thresholds while preserving the downtrend veto and late-spike filter.

Crypto paper results now label each symbol as `PAPER_ELIGIBLE`, `LEAK`, `NO_TRADE_WATCH`, or `WATCH_ONLY`. Aggregates include `eligible_symbols`, `leak_symbols`, `no_trade_symbols`, and `adaptive_candidate_symbols`. Use `config_overrides.exclude_symbols` to retest a basket after removing proven leaks, while staying paper-only.

## Verify Live Deploy

Open:

```text
https://living-screener-mcp.onrender.com/version
https://living-screener-mcp.onrender.com/tools
https://living-screener-mcp.onrender.com/config
https://living-screener-mcp.onrender.com/health
```

`/version` should show:

```json
{
  "build_version": "2026.06.09-session-loop",
  "market_data_provider": "finnhub",
  "has_finnhub_api_key": true,
  "can_place_order_from_this_mcp": false
}
```

## Local Run

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## MCP Endpoint

```text
https://living-screener-mcp.onrender.com/mcp
```

Use no auth while `HOSTED_MODE=false`. Do not send private account data while no auth is enabled.
