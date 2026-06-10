from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from app.factory import create_container
from app.models.enums import Direction, OrderType
from app.models.schemas import TradePlan
from app.utils import utc_now
from app.version import BUILD_VERSION


container = create_container()

mcp = FastMCP(
    name="Living Screener MCP",
    instructions=(
        "Use this server for market scans, signal scoring, trade planning, risk checks, journaling, "
        "postmortems, backtests, and prompt/rule evolution. This server cannot place brokerage orders, "
        "does not store Robinhood credentials, and does not call Robinhood APIs. For options review, use "
        "review_candidate_for_options so stock setup quality and options-chain quality are checked together. "
        "For pending buys, use review_pending_buy_order after 60 seconds before treating the order as still valid. "
        "For crypto paper testing, call run_backtest with engine crypto-paper-overnight; this routes to paper-only "
        "simulation and cannot place broker orders. For continuous improvement, use the learning tools to classify "
        "false positives, missed moves, good passes, and rule-change hypotheses; never auto-apply learning proposals. "
        "When U.S. options liquidity is closed or stale, use off-hours/global research tools for underlying-only study. "
        "For pre-move research, use the blueprint tools to inspect evidence modules, penalties, missing data, and "
        "options-structure mapping before changing live gates. For manual or paper option fills, use the paper ledger "
        "tools to log entries, closes, P/L, and learning labels without broker contact."
    ),
)


@mcp.tool
def get_version() -> dict:
    return _version_payload()


@mcp.tool
def version() -> dict:
    return _version_payload()


@mcp.tool
def get_build_version() -> dict:
    return _version_payload()


def _version_payload() -> dict:
    settings = container.settings
    return {
        "service": settings.app_name,
        "build_version": BUILD_VERSION,
        "market_data_provider": settings.market_data_provider,
        "has_finnhub_api_key": bool(settings.finnhub_api_key),
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
    }


@mcp.tool
def run_market_scan(mode: str, tickers: list[str] | None = None, max_candidates: int = 25) -> dict:
    return container.scanner.run_market_scan(mode, tickers, max_candidates)


@mcp.tool
def run_scalp_scan(tickers: list[str] | None = None, max_candidates: int = 25) -> dict:
    return container.scanner.run_market_scan("scalp_review", tickers, max_candidates)


@mcp.tool
def market_readiness_check(tickers: list[str] | None = None, max_candidates: int = 25) -> dict:
    return _market_readiness_check(container, tickers, max_candidates)


@mcp.tool
def run_review_harvest(tickers: list[str] | None = None, mode: str = "scalp_review", max_candidates: int = 25, review_top_n: int = 8, max_contract_price: float | None = None) -> dict:
    return _run_review_harvest(container, tickers, mode, max_candidates, review_top_n, max_contract_price)


@mcp.tool
def get_market_session_playbook(tickers: list[str] | None = None, account_value: float = 50.0) -> dict:
    return _get_market_session_playbook(container, tickers, account_value)


@mcp.tool
def run_latest_harvest_followup(limit: int = 5, classify: bool = True) -> dict:
    return _run_latest_harvest_followup(container, limit, classify)


@mcp.tool
def get_ops_command_center(tickers: list[str] | None = None, account_value: float = 50.0) -> dict:
    return _get_ops_command_center(container, tickers, account_value)


@mcp.tool
def run_morning_readiness_autopilot(tickers: list[str] | None = None, account_value: float = 50.0, max_candidates: int = 25) -> dict:
    return _run_morning_readiness_autopilot(container, tickers, account_value, max_candidates)


@mcp.tool
def run_live_review_cycle(
    tickers: list[str] | None = None,
    account_value: float = 50.0,
    max_candidates: int = 25,
    review_top_n: int = 8,
    max_contract_price: float | None = None,
    include_followup: bool = False,
) -> dict:
    return _run_live_review_cycle(container, tickers, account_value, max_candidates, review_top_n, max_contract_price, include_followup)


@mcp.tool
def analyze_ticker(ticker: str, mode: str | None = None) -> dict:
    return container.scanner.analyze_ticker(ticker, mode)


@mcp.tool
def validate_options_chain(ticker: str, direction: str = "call", max_contract_price: float | None = None) -> dict:
    return container.options.validate_chain(ticker, direction, max_contract_price)


@mcp.tool
def validate_broker_option_snapshot(snapshot: dict[str, Any], max_contract_price: float | None = None) -> dict:
    return container.options.validate_broker_snapshot(snapshot, max_contract_price)


@mcp.tool
def build_manual_trade_preflight_ticket(snapshot: dict[str, Any], account_value: float = 50.0, max_contract_price: float | None = None, notes: str = "") -> dict:
    return _build_manual_trade_preflight_ticket(container, snapshot, account_value, max_contract_price, notes)


@mcp.tool
def log_manual_option_paper_entry(ticket: dict[str, Any], fill_price: float, quantity: int = 1, underlying_price: float | None = None, notes: str = "") -> dict:
    return _log_manual_option_paper_entry(container, ticket, fill_price, quantity, underlying_price, notes)


@mcp.tool
def close_manual_option_paper_trade(entry_id: int | None = None, contract_symbol: str | None = None, exit_price: float = 0.0, exit_reason: str = "manual_close", notes: str = "") -> dict:
    return _close_manual_option_paper_trade(container, entry_id, contract_symbol, exit_price, exit_reason, notes)


@mcp.tool
def summarize_manual_option_paper_trades(limit: int = 100) -> dict:
    return _summarize_manual_option_paper_trades(container, limit)


@mcp.tool
def review_pending_buy_order(ticker: str, submitted_at: str, limit_price: float | None = None, is_options_order: bool = False, direction: str = "call", mode: str = "conservative_review_only") -> dict:
    return container.pending_orders.review_pending_buy(ticker, submitted_at, limit_price, is_options_order, direction, mode)


@mcp.tool
def review_candidate_for_options(ticker: str, direction: str = "call", mode: str = "conservative_review_only", max_contract_price: float | None = None) -> dict:
    return _review_candidate_for_options(container, ticker, direction, mode, max_contract_price)


@mcp.tool
def build_setup_fingerprint(snapshot: dict[str, Any]) -> dict:
    return container.setup_memory.build_fingerprint(snapshot)


@mcp.tool
def compare_setup_memory(snapshot: dict[str, Any], limit: int = 100) -> dict:
    return container.setup_memory.compare_snapshot(snapshot, limit)


def _market_readiness_check(service_container, tickers: list[str] | None, max_candidates: int) -> dict:
    max_candidates = max(1, min(int(max_candidates or 25), 50))
    scan = service_container.scanner.run_market_scan("scalp_review", tickers, max_candidates)
    rows = (scan.get("top_candidates") or []) + (scan.get("pass_list") or [])
    valid_rows = [row for row in rows if row.get("data_status") == "valid"]
    stale_rows = [
        row
        for row in rows
        if any("stale" in str(reason).lower() for reason in (row.get("reasons") or []))
    ]
    quote_problem_rows = [
        row
        for row in rows
        if any("quote" in str(reason).lower() for reason in (row.get("reasons") or []))
    ]
    candidate_count = len(scan.get("top_candidates") or [])
    if not rows:
        status = "MARKET_READINESS_UNKNOWN"
        next_step = "No rows returned; verify provider and watchlist."
    elif not valid_rows:
        status = "MARKET_DATA_BLOCKED"
        next_step = "Do not review options; fix quote/candle availability first."
    elif candidate_count == 0:
        status = "MARKET_DATA_READY_NO_CANDIDATES"
        next_step = "Keep harvesting; no stock setup cleared the gate yet."
    else:
        status = "MARKET_REVIEW_READY"
        next_step = "Run review harvest and only rank candidates that pass stock and small-account options gates."
    payload = {
        "status": status,
        "build_version": BUILD_VERSION,
        "mode": "scalp_review",
        "data_provider": scan.get("data_provider"),
        "data_status": scan.get("data_status"),
        "checked_tickers": [row.get("ticker") for row in rows],
        "row_count": len(rows),
        "valid_row_count": len(valid_rows),
        "candidate_count": candidate_count,
        "pass_count": len(scan.get("pass_list") or []),
        "stale_row_count": len(stale_rows),
        "quote_problem_count": len(quote_problem_rows),
        "top_stock_candidates": [_stock_summary(row) for row in (scan.get("top_candidates") or [])],
        "next_step": next_step,
        "scan_summary": _scan_summary(scan),
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "notes": [
            "Readiness can run a scan, but it does not create a trade plan or broker action.",
            "Options should only be reviewed after stock setup quality is valid and direction is clear.",
        ],
    }
    return service_container.events.log("market_readiness", payload)


def _run_review_harvest(service_container, tickers: list[str] | None, mode: str, max_candidates: int, review_top_n: int, max_contract_price: float | None) -> dict:
    max_candidates = max(1, min(int(max_candidates or 25), 50))
    review_top_n = max(1, min(int(review_top_n or 8), 20))
    scan = service_container.scanner.run_market_scan(mode, tickers, max_candidates)
    stock_candidates = [
        row
        for row in (scan.get("top_candidates") or [])
        if row.get("status") == "CANDIDATE"
        and (row.get("quality_gates") or {}).get("stock_setup_quality") == "VALID_CANDIDATE"
        and str(row.get("direction") or "").lower() in {"long", "short"}
    ]
    reviews: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for candidate in stock_candidates[:review_top_n]:
        direction = str(candidate.get("direction") or "").lower()
        option_direction = "call" if direction == "long" else "put"
        review = _review_candidate_for_options(
            service_container,
            str(candidate.get("ticker") or ""),
            option_direction,
            mode,
            max_contract_price,
        )
        reviews.append(review)

    for candidate in (scan.get("top_candidates") or []):
        if candidate not in stock_candidates:
            skipped.append(
                {
                    "ticker": candidate.get("ticker"),
                    "reason": "Skipped because stock setup was not a valid directional candidate.",
                    "status": candidate.get("status"),
                    "direction": candidate.get("direction"),
                    "quality_gates": candidate.get("quality_gates"),
                }
            )

    ready_reviews = [
        review
        for review in reviews
        if review.get("status") == "REVIEW_ONLY_OPTIONS_READY"
        and (review.get("small_account_review") or {}).get("status") == "SMALL_ACCOUNT_SCALP_ACCEPTABLE"
    ]
    ranked = sorted(ready_reviews, key=_review_rank_key, reverse=True)
    watch_only = [review for review in reviews if review not in ready_reviews]
    status = "REVIEW_HARVEST_READY" if ranked else "NO_TRADE_PLAN"
    payload = {
        "status": status,
        "build_version": BUILD_VERSION,
        "mode": mode,
        "scan_summary": _scan_summary(scan),
        "reviewed_count": len(reviews),
        "eligible_count": len(ranked),
        "watch_only_count": len(watch_only),
        "skipped_count": len(skipped),
        "ranked_candidates": [_review_summary(review) for review in ranked],
        "watch_only": [_review_summary(review) for review in watch_only],
        "skipped": skipped,
        "followup_checks": [_review_followup(review) for review in ranked[:5]],
        "raw_reviews": reviews,
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "order_allowed": False,
        "notes": [
            "Harvest ranks only candidates that passed stock setup and SMALL_ACCOUNT_SCALP_ACCEPTABLE.",
            "This is still review-only; broker review and manual decision remain required.",
            "Use followup_checks after 15/30/60 minutes to classify whether the review helped or hurt.",
        ],
    }
    return service_container.events.log("review_harvest", payload)


def _get_market_session_playbook(service_container, tickers: list[str] | None, account_value: float) -> dict:
    universe = tickers or list(service_container.settings.scalp_watchlist)
    ticker_query = ",".join(universe)
    account_value = _float_or_zero(account_value) or 50.0
    max_contract = service_container.settings.scalp_max_contract_price
    payload = {
        "status": "SESSION_PLAYBOOK_READY",
        "build_version": BUILD_VERSION,
        "generated_at": utc_now(),
        "timezone": "America/Chicago",
        "target": "Review-only live-market workflow for the next U.S. regular session.",
        "universe": universe,
        "account_value_reference": account_value,
        "small_account_contract_cap": max_contract,
        "safety": {
            "review_only": True,
            "place_orders": False,
            "market_orders_allowed": False,
            "manual_approval_required": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        },
        "session_blocks": [
            {
                "label": "Pre-market setup",
                "central_time": "07:45-08:25",
                "intent": "Confirm deployment, safety, data provider, and watchlist before options liquidity matters.",
                "actions": [
                    "/version",
                    f"/health/full?expected_build_version={BUILD_VERSION}",
                    f"/debug/scan-schema?expected_build_version={BUILD_VERSION}",
                    f"/ops/market-readiness?tickers={ticker_query}&max_candidates=25",
                ],
                "pass_condition": "Build matches, safety is review-only, and readiness is not MARKET_DATA_BLOCKED.",
                "fail_condition": "Wrong build, stale data during regular market, quote/candle failure across the universe, or missing safety flags.",
            },
            {
                "label": "Opening stabilization",
                "central_time": "08:30-08:50",
                "intent": "Let spreads and first candles stabilize; gather readiness only.",
                "actions": [
                    f"/ops/market-readiness?tickers={ticker_query}&max_candidates=25",
                ],
                "pass_condition": "Fresh data appears and stock candidates are not forced into options review too early.",
                "fail_condition": "Wide opening noise, stale quotes, or no valid rows.",
            },
            {
                "label": "First review harvest",
                "central_time": "08:50-10:15",
                "intent": "Run harvest loops, rank only candidates that pass stock and small-account options gates.",
                "actions": [
                    f"/ops/review-harvest?tickers={ticker_query}&max_candidates=25&review_top_n=8&max_contract_price={max_contract}",
                    "/ops/harvest-followup?limit=5&classify=true",
                ],
                "pass_condition": "At least one REVIEW_ONLY_OPTIONS_READY candidate with SMALL_ACCOUNT_SCALP_ACCEPTABLE and manageable friction.",
                "fail_condition": "NO_TRADE_PLAN, options-chain gaps, high friction, VWAP conflict, or setup memory warning from similar risk.",
            },
            {
                "label": "Midday caution",
                "central_time": "10:15-12:30",
                "intent": "Prefer learning and watchlist maintenance unless a setup remains unusually clean.",
                "actions": [
                    "/learning/dashboard",
                    f"/ops/market-readiness?tickers={ticker_query}&max_candidates=25",
                ],
                "pass_condition": "Only continue if data is fresh and momentum/participation remains clear.",
                "fail_condition": "Chop, collapsing RVOL, spread widening, or no clean follow-through.",
            },
            {
                "label": "Afternoon decision window",
                "central_time": "12:30-14:15",
                "intent": "Use the strictest manual review window for possible small number of carefully gated trades.",
                "actions": [
                    f"/ops/review-harvest?tickers={ticker_query}&max_candidates=25&review_top_n=8&max_contract_price={max_contract}",
                    "/review/options?ticker=REPLACE&direction=put&mode=scalp_review&format=html",
                    "/review/broker-option-snapshot",
                ],
                "pass_condition": "Stock setup, options chain, friction, setup memory, broker-visible quote, and risk limit all agree.",
                "fail_condition": "Any gate unclear. PASS is the default.",
            },
            {
                "label": "After-action learning",
                "central_time": "After each review and after close",
                "intent": "Classify what helped, hurt, faded, or was missed.",
                "actions": [
                    "/ops/harvest-followup?limit=5&classify=true",
                    "/learning/dashboard",
                    "/learning/proposals",
                ],
                "pass_condition": "Outcomes and classifications are logged without auto-applying rule changes.",
                "fail_condition": "Outcome unavailable; keep the review as unclassified rather than inventing a lesson.",
            },
        ],
        "manual_trade_gate": [
            "Build and safety confirmed.",
            "Harvest candidate is REVIEW_ONLY_OPTIONS_READY.",
            "Small-account gate is SMALL_ACCOUNT_SCALP_ACCEPTABLE.",
            "Friction band is not BLOCKED_BY_FRICTION.",
            "Setup memory does not show repeated similar risk.",
            "Broker-visible option snapshot matches or improves the MCP quote.",
            "No market order; limit-only review.",
            "Manual approval phrase remains required outside this MCP.",
        ],
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "notes": [
            "This is an operating checklist, not a trade recommendation.",
            "The MCP cannot execute; every broker action remains manual and separate.",
        ],
    }
    return service_container.events.log("session_playbook", payload)


def _run_latest_harvest_followup(service_container, limit: int, classify: bool) -> dict:
    limit = max(1, min(int(limit or 5), 20))
    recent = service_container.events.recent("review_harvest", 1)
    if not recent:
        return service_container.events.log(
            "harvest_followup",
            {
                "status": "NO_HARVEST_TO_FOLLOW_UP",
                "reason": "No review_harvest event has been logged yet.",
                "outcomes": [],
                "classifications": [],
                "review_only": True,
                "can_place_order_from_this_mcp": False,
                "can_cancel_order_from_this_mcp": False,
            },
        )

    harvest_event = recent[0]
    harvest = harvest_event.get("payload") or {}
    raw_reviews = harvest.get("raw_reviews") or []
    checks = harvest.get("followup_checks") or []
    raw_by_ticker = {str(review.get("ticker") or "").upper(): review for review in raw_reviews if isinstance(review, dict)}
    outcomes: list[dict[str, Any]] = []
    classifications: list[dict[str, Any]] = []
    for check in checks[:limit]:
        ticker = str(check.get("ticker") or "").upper()
        review = {
            "review_id": f"{ticker}-{check.get('direction')}-{check.get('entry_reference')}",
            "ticker": ticker,
            "direction": check.get("direction"),
            "entry_reference": check.get("entry_reference"),
            "review_timestamp": check.get("review_timestamp"),
            "contract_symbol": check.get("contract_symbol"),
        }
        outcome = service_container.review_outcomes.check_review_outcome(review, {"15m": 3, "30m": 6, "60m": 12})
        outcomes.append(outcome)
        snapshot = raw_by_ticker.get(ticker) or check
        if classify:
            classifications.append(service_container.learning.classify_review_outcome(snapshot, outcome))

    summary = service_container.review_outcomes.summarize_review_outcomes(outcomes) if outcomes else None
    learning_summary = service_container.learning.summarize_learning(classifications, limit) if classifications else None
    payload = {
        "status": "HARVEST_FOLLOWUP_COMPLETE" if outcomes else "HARVEST_FOLLOWUP_EMPTY",
        "build_version": BUILD_VERSION,
        "harvest_event_id": harvest_event.get("id"),
        "harvest_timestamp": harvest_event.get("timestamp"),
        "checks_requested": len(checks),
        "checks_completed": len(outcomes),
        "classify": bool(classify),
        "outcomes": outcomes,
        "classifications": classifications,
        "outcome_summary": summary,
        "learning_summary": learning_summary,
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "notes": [
            "Follow-up grades prior review-only harvest candidates.",
            "If market data is unavailable, outcomes are logged as unavailable rather than forced.",
            "Classifications are learning labels only; rule proposals still require manual review and backtesting.",
        ],
    }
    return service_container.events.log("harvest_followup", payload)


def _get_ops_command_center(service_container, tickers: list[str] | None, account_value: float) -> dict:
    universe = tickers or list(service_container.settings.scalp_watchlist)
    ticker_query = ",".join(universe)
    latest_readiness = _latest_payload(service_container, "market_readiness")
    latest_harvest = _latest_payload(service_container, "review_harvest")
    latest_followup = _latest_payload(service_container, "harvest_followup")
    latest_learning = _latest_payload(service_container, "learning_summary")
    recent_classifications = [
        event.get("payload") or {}
        for event in service_container.events.recent("learning_outcome_classification", 25)
    ]
    status, next_action = _command_center_status(latest_readiness, latest_harvest, latest_followup)
    payload = {
        "status": status,
        "build_version": BUILD_VERSION,
        "generated_at": utc_now(),
        "mode": "review_only_command_center",
        "universe": universe,
        "account_value_reference": _float_or_zero(account_value) or 50.0,
        "safety": {
            "review_only": True,
            "place_orders": False,
            "market_orders_allowed": False,
            "manual_approval_required": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        },
        "latest": {
            "market_readiness": _compact_event(latest_readiness),
            "review_harvest": _compact_event(latest_harvest),
            "harvest_followup": _compact_event(latest_followup),
            "learning_summary": _compact_event(latest_learning),
        },
        "counts": {
            "market_readiness": service_container.events.count("market_readiness"),
            "review_harvest": service_container.events.count("review_harvest"),
            "harvest_followup": service_container.events.count("harvest_followup"),
            "learning_classifications": service_container.events.count("learning_outcome_classification"),
            "review_outcomes": service_container.events.count("review_outcome"),
        },
        "latest_learning_labels": [
            {
                "ticker": item.get("ticker"),
                "classification": item.get("classification"),
                "lesson_tags": item.get("lesson_tags") or [],
                "reason": item.get("reason"),
            }
            for item in recent_classifications[:10]
        ],
        "next_action": next_action,
        "action_links": {
            "session_playbook": f"/ops/session-playbook?tickers={ticker_query}&account_value={_float_or_zero(account_value) or 50.0}",
            "market_readiness": f"/ops/market-readiness?tickers={ticker_query}&max_candidates=25",
            "review_harvest": f"/ops/review-harvest?tickers={ticker_query}&max_candidates=25&review_top_n=8&max_contract_price={service_container.settings.scalp_max_contract_price}",
            "harvest_followup": "/ops/harvest-followup?limit=5&classify=true",
            "learning_dashboard": "/learning/dashboard",
            "paper_option_summary": "/paper/options/summary",
            "debug_health": f"/health/full?expected_build_version={BUILD_VERSION}",
            "debug_schema": f"/debug/scan-schema?expected_build_version={BUILD_VERSION}",
        },
        "manual_trade_gate": [
            "Command center build and safety are confirmed.",
            "Market readiness is not blocked.",
            "Harvest candidate is REVIEW_ONLY_OPTIONS_READY.",
            "Small-account gate is SMALL_ACCOUNT_SCALP_ACCEPTABLE.",
            "Friction and setup memory are acceptable.",
            "Broker-visible option snapshot validates the contract.",
            "Risk limit check passes.",
            "No market orders; broker action remains manual and outside this MCP.",
        ],
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "notes": [
            "Command center reads recent logs; it does not run scans by itself.",
            "Use the action links to advance the loop deliberately.",
            "PASS remains the default whenever data, options quality, friction, memory, or risk is unclear.",
        ],
    }
    return service_container.events.log("ops_command_center", payload)


def _run_morning_readiness_autopilot(service_container, tickers: list[str] | None, account_value: float, max_candidates: int) -> dict:
    max_candidates = max(1, min(int(max_candidates or 25), 50))
    universe = [str(ticker).upper().strip() for ticker in (tickers or service_container.settings.default_tickers) if str(ticker).strip()]
    readiness = _market_readiness_check(service_container, universe, max_candidates)
    playbook = _get_market_session_playbook(service_container, universe, account_value)
    command_center = _get_ops_command_center(service_container, universe, account_value)
    paper_ledger = _summarize_manual_option_paper_trades(service_container, 100)
    readiness_status = readiness.get("status")
    command_status = command_center.get("status")
    if readiness_status == "MARKET_DATA_BLOCKED":
        status = "AUTOPILOT_DATA_BLOCKED"
        next_action = "Wait for cleaner data or fix quote/candle provider before reviewing options."
    elif readiness_status == "MARKET_REVIEW_READY":
        status = "AUTOPILOT_READY_FOR_HARVEST"
        next_action = "Run review harvest, then options-review only valid directional stock candidates."
    elif readiness_status == "MARKET_DATA_READY_NO_CANDIDATES":
        status = "AUTOPILOT_KEEP_SCANNING"
        next_action = "Keep readiness/harvest cadence; do not force a setup without stock candidates."
    elif command_status == "HARVEST_READY_NEEDS_FOLLOWUP":
        status = "AUTOPILOT_NEEDS_FOLLOWUP"
        next_action = "Run harvest follow-up before trusting stale candidate context."
    else:
        status = "AUTOPILOT_STANDBY"
        next_action = "Confirm build/safety and rerun readiness near the next market window."
    payload = {
        "status": status,
        "build_version": BUILD_VERSION,
        "mode": "morning_readiness_autopilot",
        "generated_at": utc_now(),
        "universe": universe,
        "account_value_reference": account_value,
        "safety": {
            "review_only": True,
            "place_orders": False,
            "market_orders_allowed": False,
            "manual_approval_required": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        },
        "readiness": _compact_autopilot_result(readiness),
        "command_center": _compact_autopilot_result(command_center),
        "paper_ledger": {
            "status": paper_ledger.get("status"),
            "entry_count": paper_ledger.get("entry_count"),
            "open_count": paper_ledger.get("open_count"),
            "closed_count": paper_ledger.get("closed_count"),
            "win_rate": paper_ledger.get("win_rate"),
            "total_pnl_dollars": paper_ledger.get("total_pnl_dollars"),
        },
        "session_blocks": playbook.get("session_blocks") or [],
        "manual_trade_gate": playbook.get("manual_trade_gate") or [],
        "next_action": next_action,
        "action_links": {
            "command_center": f"/ops/command-center?tickers={','.join(universe)}&account_value={_float_or_zero(account_value) or 50.0}",
            "market_readiness": f"/ops/market-readiness?tickers={','.join(universe)}&max_candidates={max_candidates}",
            "review_harvest": f"/ops/review-harvest?tickers={','.join(universe)}&max_candidates={max_candidates}&review_top_n=8&max_contract_price={service_container.settings.scalp_max_contract_price}",
            "harvest_followup": "/ops/harvest-followup?limit=5&classify=true",
            "paper_ledger": "/paper/options/summary",
            "debug_health": f"/health/full?expected_build_version={BUILD_VERSION}",
            "debug_schema": f"/debug/scan-schema?expected_build_version={BUILD_VERSION}",
        },
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "notes": [
            "Autopilot runs readiness and summarizes the operating loop; it does not place, submit, simulate, modify, or cancel broker orders.",
            "Only rank candidates after stock setup and SMALL_ACCOUNT_SCALP_ACCEPTABLE both pass.",
            "Use the paper ledger to record manual/paper outcomes so the mistake engine can learn after the fact.",
        ],
    }
    return service_container.events.log("morning_readiness_autopilot", payload)


def _run_live_review_cycle(
    service_container,
    tickers: list[str] | None,
    account_value: float,
    max_candidates: int,
    review_top_n: int,
    max_contract_price: float | None,
    include_followup: bool,
) -> dict:
    max_candidates = max(1, min(int(max_candidates or 25), 50))
    review_top_n = max(1, min(int(review_top_n or 8), 20))
    universe = [str(ticker).upper().strip() for ticker in (tickers or service_container.settings.default_tickers) if str(ticker).strip()]
    effective_contract_cap = max_contract_price
    if effective_contract_cap is None:
        effective_contract_cap = service_container.settings.scalp_max_contract_price
    readiness = _market_readiness_check(service_container, universe, max_candidates)
    harvest: dict[str, Any] | None = None
    followup: dict[str, Any] | None = None
    if readiness.get("status") not in {"MARKET_DATA_BLOCKED", "MARKET_READINESS_UNKNOWN"}:
        harvest = _run_review_harvest(
            service_container,
            universe,
            "scalp_review",
            max_candidates,
            review_top_n,
            effective_contract_cap,
        )
        if include_followup:
            followup = _run_latest_harvest_followup(service_container, 5, True)

    paper_ledger = _summarize_manual_option_paper_trades(service_container, 100)
    ranked_candidates = (harvest or {}).get("ranked_candidates") or []
    if readiness.get("status") == "MARKET_DATA_BLOCKED":
        status = "LIVE_CYCLE_DATA_BLOCKED"
        next_action = "Do not review options; wait for clean quote/candle data."
    elif not harvest:
        status = "LIVE_CYCLE_STANDBY"
        next_action = "Rerun readiness near the next market window."
    elif ranked_candidates:
        status = "LIVE_CYCLE_CANDIDATES_READY"
        next_action = "Manually inspect the top candidate in broker, then run manual preflight with broker-visible bid/ask/volume/OI."
    else:
        status = "NO_TRADE_PLAN"
        next_action = "No candidate passed both stock setup and small-account options gates. Keep scanning; do not force a trade."

    payload = {
        "status": status,
        "build_version": BUILD_VERSION,
        "mode": "live_review_cycle",
        "generated_at": utc_now(),
        "universe": universe,
        "account_value_reference": account_value,
        "max_candidates": max_candidates,
        "review_top_n": review_top_n,
        "max_contract_price_used": effective_contract_cap,
        "readiness": _compact_autopilot_result(readiness),
        "harvest": _compact_harvest_for_cycle(harvest),
        "ranked_candidates": ranked_candidates,
        "watch_only_reviews": (harvest or {}).get("watch_only") or [],
        "skipped_candidates": (harvest or {}).get("skipped") or [],
        "paper_ledger": {
            "status": paper_ledger.get("status"),
            "entry_count": paper_ledger.get("entry_count"),
            "open_count": paper_ledger.get("open_count"),
            "closed_count": paper_ledger.get("closed_count"),
            "win_rate": paper_ledger.get("win_rate"),
            "total_pnl_dollars": paper_ledger.get("total_pnl_dollars"),
        },
        "followup": _compact_autopilot_result(followup),
        "next_action": next_action,
        "manual_preflight_required": bool(ranked_candidates),
        "manual_trade_gate": [
            "Live review cycle status is LIVE_CYCLE_CANDIDATES_READY.",
            "Candidate status is REVIEW_ONLY_OPTIONS_READY.",
            "Small-account gate is SMALL_ACCOUNT_SCALP_ACCEPTABLE.",
            "Broker-visible contract snapshot still matches or improves the reviewed contract.",
            "Manual preflight returns MANUAL_PREFLIGHT_READY.",
            "No market order; any broker action is manual and outside this MCP.",
            "If a buy sits pending for more than 60 seconds, re-review it before trusting it.",
        ],
        "action_links": {
            "morning_autopilot": f"/ops/morning-autopilot?tickers={','.join(universe)}&account_value={_float_or_zero(account_value) or 50.0}&max_candidates={max_candidates}",
            "live_review_cycle": f"/ops/live-review-cycle?tickers={','.join(universe)}&account_value={_float_or_zero(account_value) or 50.0}&max_candidates={max_candidates}&review_top_n={review_top_n}&max_contract_price={effective_contract_cap}",
            "review_harvest": f"/ops/review-harvest?tickers={','.join(universe)}&max_candidates={max_candidates}&review_top_n={review_top_n}&max_contract_price={effective_contract_cap}",
            "manual_preflight": "/review/manual-preflight",
            "paper_ledger": "/paper/options/summary",
            "harvest_followup": "/ops/harvest-followup?limit=5&classify=true",
        },
        "safety": {
            "review_only": True,
            "place_orders": False,
            "market_orders_allowed": False,
            "manual_approval_required": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        },
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "notes": [
            "This cycle can run market data review and options review, but cannot create broker action.",
            "NO_TRADE_PLAN is the expected result whenever stock setup, options quality, small-account friction, or data quality is not strong enough.",
            "Use paper ledger entry/close to learn from manual or hypothetical choices after the fact.",
        ],
    }
    return service_container.events.log("live_review_cycle", payload)


def _build_manual_trade_preflight_ticket(service_container, snapshot: dict[str, Any], account_value: float, max_contract_price: float | None, notes: str = "") -> dict:
    account_value = _float_or_zero(account_value) or 50.0
    effective_max_contract_price = max_contract_price
    if effective_max_contract_price is None:
        effective_max_contract_price = service_container.settings.scalp_max_contract_price
    option_validation = service_container.options.validate_broker_snapshot(snapshot, effective_max_contract_price)
    accepted_contracts = option_validation.get("accepted_contracts") or []
    selected = accepted_contracts[0] if accepted_contracts else None
    ticker = str(option_validation.get("ticker") or snapshot.get("ticker") or snapshot.get("underlying") or "").upper()
    direction = str(option_validation.get("direction") or snapshot.get("direction") or "call").lower()
    normalized_direction = Direction.SHORT if direction in {"put", "puts", "short"} else Direction.LONG
    proposed_risk = _float_or_zero((selected or {}).get("max_loss_dollars"))
    risk_plan = TradePlan(
        ticker=ticker or "UNKNOWN",
        direction=normalized_direction,
        setup_type="manual_options_preflight",
        account_value=account_value,
        proposed_risk_dollars=proposed_risk,
        order_type=OrderType.LIMIT,
        is_options_trade=True,
        is_zero_dte=bool(selected and int(selected.get("days_to_expiration") or 0) <= 0),
        requested_execution=False,
        approval_text=None,
    )
    risk_check = service_container.risk.check(risk_plan)
    blocking_reasons: list[str] = []
    warnings: list[str] = []
    if option_validation.get("status") != "OPTIONS_CHAIN_ACCEPTABLE":
        blocking_reasons.append("Broker-visible option snapshot failed options quality validation.")
    if not selected:
        blocking_reasons.append("No accepted contract is available from the broker snapshot.")
    if risk_check.get("status") != "APPROVE_FOR_REVIEW":
        blocking_reasons.extend(risk_check.get("reasons") or ["Risk check blocked this review."])
    if selected and selected.get("spread_pct") is not None and float(selected.get("spread_pct") or 0) > 0.08:
        warnings.append("Spread is wider than preferred; use limit-only discipline and do not chase.")
    if selected and int(selected.get("days_to_expiration") or 0) <= 1:
        warnings.append("1DTE or less has elevated decay/whipsaw risk.")
    status = "MANUAL_PREFLIGHT_READY" if not blocking_reasons else "NO_TRADE_PLAN"
    payload = {
        "status": status,
        "build_version": BUILD_VERSION,
        "ticker": ticker,
        "direction": "put" if normalized_direction == Direction.SHORT else "call",
        "account_value_reference": account_value,
        "max_contract_price_used": effective_max_contract_price,
        "selected_contract": selected,
        "option_validation": option_validation,
        "risk_check": risk_check,
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
        "manual_ticket": {
            "contract_symbol": (selected or {}).get("contract_symbol"),
            "order_type": "limit_only",
            "max_review_ask": (selected or {}).get("ask"),
            "max_loss_dollars": (selected or {}).get("max_loss_dollars"),
            "quantity": 1 if selected else 0,
            "broker_action_required": True if status == "MANUAL_PREFLIGHT_READY" else False,
            "mcp_can_execute": False,
            "approval_phrase_required_outside_mcp": service_container.settings.approval_phrase,
        },
        "checklist": [
            "Confirm the broker screen still matches this contract symbol.",
            "Confirm bid/ask, volume, open interest, DTE, and max loss still pass.",
            "Use limit-only review; no market orders.",
            "Do not chase if spread widens or underlying setup weakens.",
            "If placed manually outside this MCP, recheck any pending buy after 60 seconds.",
        ],
        "notes": notes,
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "order_allowed": False,
    }
    return service_container.events.log("manual_preflight_ticket", payload)


def _log_manual_option_paper_entry(service_container, ticket: dict[str, Any], fill_price: float, quantity: int, underlying_price: float | None, notes: str = "") -> dict:
    fill = _float_or_zero(fill_price)
    quantity = max(1, int(quantity or 1))
    if fill <= 0:
        return service_container.events.log(
            "manual_option_paper_entry",
            {
                "status": "PAPER_ENTRY_REJECTED",
                "reason": "Positive fill_price is required.",
                "review_only": True,
                "can_place_order_from_this_mcp": False,
                "can_cancel_order_from_this_mcp": False,
            },
        )
    selected = ticket.get("selected_contract") or {}
    manual_ticket = ticket.get("manual_ticket") or {}
    contract_symbol = str(
        manual_ticket.get("contract_symbol")
        or selected.get("contract_symbol")
        or ticket.get("contract_symbol")
        or ""
    )
    ticker = str(ticket.get("ticker") or selected.get("ticker") or "").upper()
    direction = str(ticket.get("direction") or selected.get("direction") or "").lower()
    max_loss = round(fill * 100 * quantity, 2)
    payload = {
        "status": "PAPER_OPTION_ENTRY_OPEN",
        "build_version": BUILD_VERSION,
        "ticker": ticker,
        "direction": direction,
        "contract_symbol": contract_symbol,
        "entry_price": fill,
        "quantity": quantity,
        "entry_debit_dollars": max_loss,
        "underlying_entry_price": underlying_price,
        "entry_timestamp": utc_now(),
        "source_ticket_status": ticket.get("status"),
        "source_preflight": ticket,
        "notes": notes,
        "paper_only": True,
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "order_placed": False,
        "order_submitted": False,
        "broker_action": False,
    }
    if ticket.get("status") not in {"MANUAL_PREFLIGHT_READY", "REVIEW_ONLY_OPTIONS_READY"}:
        payload["status"] = "PAPER_ENTRY_LOGGED_FROM_UNREADY_TICKET"
        payload["warning"] = "Source ticket was not ready; entry is logged for study only."
    return service_container.events.log("manual_option_paper_entry", payload)


def _close_manual_option_paper_trade(service_container, entry_id: int | None, contract_symbol: str | None, exit_price: float, exit_reason: str, notes: str = "") -> dict:
    exit_value = _float_or_zero(exit_price)
    if exit_value < 0:
        return service_container.events.log(
            "manual_option_paper_close",
            {
                "status": "PAPER_CLOSE_REJECTED",
                "reason": "exit_price cannot be negative.",
                "review_only": True,
                "can_place_order_from_this_mcp": False,
                "can_cancel_order_from_this_mcp": False,
            },
        )
    entry_event = _find_open_paper_entry(service_container, entry_id, contract_symbol)
    if not entry_event:
        return service_container.events.log(
            "manual_option_paper_close",
            {
                "status": "PAPER_ENTRY_NOT_FOUND",
                "reason": "No matching open paper option entry was found.",
                "entry_id": entry_id,
                "contract_symbol": contract_symbol,
                "review_only": True,
                "can_place_order_from_this_mcp": False,
                "can_cancel_order_from_this_mcp": False,
            },
        )
    entry = entry_event.get("payload") or {}
    entry_price = _float_or_zero(entry.get("entry_price"))
    quantity = max(1, int(entry.get("quantity") or 1))
    pnl = round((exit_value - entry_price) * 100 * quantity, 2)
    return_pct = round((exit_value - entry_price) / entry_price, 5) if entry_price > 0 else None
    outcome = {
        "verdict": "HELPED" if pnl > 0 else "HURT" if pnl < 0 else "FLAT",
        "current_return_pct": return_pct,
        "max_favorable_excursion": return_pct if return_pct and return_pct > 0 else None,
        "max_adverse_excursion": return_pct if return_pct and return_pct < 0 else None,
        "outcome_window_status": "PAPER_OPTION_CLOSE",
    }
    snapshot = entry.get("source_preflight") or entry
    classification = service_container.learning.classify_review_outcome(snapshot, outcome)
    payload = {
        "status": "PAPER_OPTION_CLOSED",
        "build_version": BUILD_VERSION,
        "entry_event_id": entry_event.get("id"),
        "ticker": entry.get("ticker"),
        "direction": entry.get("direction"),
        "contract_symbol": entry.get("contract_symbol"),
        "entry_price": entry_price,
        "exit_price": exit_value,
        "quantity": quantity,
        "pnl_dollars": pnl,
        "return_pct": return_pct,
        "exit_reason": exit_reason,
        "exit_timestamp": utc_now(),
        "outcome": outcome,
        "learning_classification": classification,
        "notes": notes,
        "paper_only": True,
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "order_placed": False,
        "order_submitted": False,
        "broker_action": False,
    }
    service_container.journal.log_trade_result(payload)
    return service_container.events.log("manual_option_paper_close", payload)


def _summarize_manual_option_paper_trades(service_container, limit: int = 100) -> dict:
    limit = max(1, min(int(limit or 100), 500))
    entries = [
        event
        for event in service_container.events.recent("manual_option_paper_entry", limit)
        if (event.get("payload") or {}).get("status") in {"PAPER_OPTION_ENTRY_OPEN", "PAPER_ENTRY_LOGGED_FROM_UNREADY_TICKET"}
    ]
    closes = [
        event
        for event in service_container.events.recent("manual_option_paper_close", limit)
        if (event.get("payload") or {}).get("status") == "PAPER_OPTION_CLOSED"
    ]
    closed_entry_ids = {
        (event.get("payload") or {}).get("entry_event_id")
        for event in closes
    }
    open_entries = [event for event in entries if event.get("id") not in closed_entry_ids]
    pnls = [_float_or_zero((event.get("payload") or {}).get("pnl_dollars")) for event in closes]
    wins = [value for value in pnls if value > 0]
    payload = {
        "status": "PAPER_LEDGER_READY",
        "build_version": BUILD_VERSION,
        "entry_count": len(entries),
        "closed_count": len(closes),
        "open_count": len(open_entries),
        "win_rate": round(len(wins) / len(pnls), 4) if pnls else 0.0,
        "total_pnl_dollars": round(sum(pnls), 2),
        "average_pnl_dollars": round(sum(pnls) / len(pnls), 2) if pnls else 0.0,
        "open_entries": [
            {
                "entry_event_id": event.get("id"),
                "timestamp": event.get("timestamp"),
                "ticker": (event.get("payload") or {}).get("ticker"),
                "contract_symbol": (event.get("payload") or {}).get("contract_symbol"),
                "entry_price": (event.get("payload") or {}).get("entry_price"),
                "quantity": (event.get("payload") or {}).get("quantity"),
            }
            for event in open_entries[:20]
        ],
        "recent_closes": [
            {
                "entry_event_id": (event.get("payload") or {}).get("entry_event_id"),
                "timestamp": event.get("timestamp"),
                "ticker": (event.get("payload") or {}).get("ticker"),
                "contract_symbol": (event.get("payload") or {}).get("contract_symbol"),
                "pnl_dollars": (event.get("payload") or {}).get("pnl_dollars"),
                "return_pct": (event.get("payload") or {}).get("return_pct"),
                "classification": ((event.get("payload") or {}).get("learning_classification") or {}).get("classification"),
            }
            for event in closes[:20]
        ],
        "paper_only": True,
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "notes": "Paper/manual ledger only. It never contacts a broker and never proves an order existed.",
    }
    return service_container.events.log("manual_option_paper_summary", payload)


def _find_open_paper_entry(service_container, entry_id: int | None, contract_symbol: str | None) -> dict[str, Any] | None:
    entries = service_container.events.recent("manual_option_paper_entry", 500)
    closes = service_container.events.recent("manual_option_paper_close", 500)
    closed_ids = {
        (event.get("payload") or {}).get("entry_event_id")
        for event in closes
        if (event.get("payload") or {}).get("status") == "PAPER_OPTION_CLOSED"
    }
    normalized_contract = str(contract_symbol or "").upper()
    for event in entries:
        payload = event.get("payload") or {}
        if event.get("id") in closed_ids:
            continue
        if payload.get("status") not in {"PAPER_OPTION_ENTRY_OPEN", "PAPER_ENTRY_LOGGED_FROM_UNREADY_TICKET"}:
            continue
        if entry_id is not None and int(event.get("id") or 0) == int(entry_id):
            return event
        if normalized_contract and str(payload.get("contract_symbol") or "").upper() == normalized_contract:
            return event
    return None


def _latest_payload(service_container, event_type: str) -> dict[str, Any] | None:
    rows = service_container.events.recent(event_type, 1)
    if not rows:
        return None
    row = rows[0]
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    return {
        "id": row.get("id"),
        "timestamp": row.get("timestamp"),
        **payload,
    }


def _compact_event(event: dict[str, Any] | None) -> dict[str, Any] | None:
    if not event:
        return None
    return {
        "id": event.get("id"),
        "timestamp": event.get("timestamp"),
        "status": event.get("status"),
        "mode": event.get("mode"),
        "candidate_count": event.get("candidate_count"),
        "eligible_count": event.get("eligible_count"),
        "reviewed_count": event.get("reviewed_count"),
        "checks_completed": event.get("checks_completed"),
        "sample_size": event.get("sample_size"),
        "next_step": event.get("next_step"),
    }


def _compact_autopilot_result(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not result:
        return None
    return {
        "id": result.get("id"),
        "timestamp": result.get("timestamp"),
        "status": result.get("status"),
        "mode": result.get("mode"),
        "data_status": result.get("data_status"),
        "candidate_count": result.get("candidate_count"),
        "eligible_count": result.get("eligible_count"),
        "reviewed_count": result.get("reviewed_count"),
        "valid_row_count": result.get("valid_row_count"),
        "quote_problem_count": result.get("quote_problem_count"),
        "next_step": result.get("next_step"),
        "next_action": result.get("next_action"),
    }


def _compact_harvest_for_cycle(harvest: dict[str, Any] | None) -> dict[str, Any] | None:
    if not harvest:
        return None
    return {
        "id": harvest.get("id"),
        "timestamp": harvest.get("timestamp"),
        "status": harvest.get("status"),
        "mode": harvest.get("mode"),
        "reviewed_count": harvest.get("reviewed_count"),
        "eligible_count": harvest.get("eligible_count"),
        "watch_only_count": harvest.get("watch_only_count"),
        "skipped_count": len(harvest.get("skipped") or []),
        "scan_summary": harvest.get("scan_summary"),
        "next_step": harvest.get("next_step"),
    }


def _command_center_status(readiness: dict[str, Any] | None, harvest: dict[str, Any] | None, followup: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    if not readiness:
        return (
            "NEEDS_MARKET_READINESS",
            {
                "label": "Run market readiness.",
                "reason": "No market_readiness event is logged yet.",
                "endpoint": "/ops/market-readiness",
            },
        )
    readiness_status = readiness.get("status")
    if readiness_status == "MARKET_DATA_BLOCKED":
        return (
            "DATA_BLOCKED",
            {
                "label": "Fix or wait for data.",
                "reason": "Latest readiness says market data is blocked.",
                "endpoint": "/ops/market-readiness",
            },
        )
    if not harvest:
        return (
            "READY_FOR_HARVEST",
            {
                "label": "Run review harvest.",
                "reason": "Readiness exists, but no review_harvest event is logged yet.",
                "endpoint": "/ops/review-harvest",
            },
        )
    eligible = int(harvest.get("eligible_count") or 0)
    if eligible <= 0:
        return (
            "NO_TRADE_PLAN_KEEP_SCANNING",
            {
                "label": "Keep scanning and learning.",
                "reason": "Latest harvest produced no eligible small-account candidates.",
                "endpoint": "/ops/market-readiness",
            },
        )
    if not followup or followup.get("harvest_event_id") != harvest.get("id"):
        return (
            "HARVEST_READY_NEEDS_FOLLOWUP",
            {
                "label": "Review ranked candidates and schedule follow-up.",
                "reason": "Latest harvest has eligible candidates; follow-up is not yet tied to that harvest.",
                "endpoint": "/ops/harvest-followup",
            },
        )
    return (
        "LEARNING_LOOP_ACTIVE",
        {
            "label": "Review learning dashboard and rerun readiness when conditions change.",
            "reason": "Latest harvest has follow-up outcomes and learning labels.",
            "endpoint": "/learning/dashboard",
        },
    )


def _scan_summary(scan: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": scan.get("mode"),
        "data_provider": scan.get("data_provider"),
        "data_status": scan.get("data_status"),
        "top_candidate_count": len(scan.get("top_candidates") or []),
        "pass_count": len(scan.get("pass_list") or []),
        "market_regime": scan.get("market_regime"),
    }


def _stock_summary(row: dict[str, Any]) -> dict[str, Any]:
    signals = row.get("key_signals") or {}
    return {
        "ticker": row.get("ticker"),
        "status": row.get("status"),
        "score": row.get("score"),
        "direction": row.get("direction"),
        "relative_volume": signals.get("relative_volume"),
        "above_vwap": signals.get("above_vwap"),
        "below_vwap": signals.get("below_vwap"),
        "relative_strength_label": (signals.get("relative_strength") or {}).get("label"),
    }


def _review_rank_key(review: dict[str, Any]) -> tuple[float, float, float]:
    small = review.get("small_account_review") or {}
    selected = small.get("selected_contract") or {}
    priority = _float_or_zero(small.get("priority_score"))
    friction = _float_or_zero(small.get("friction_adjusted_score"))
    max_loss = _float_or_zero(selected.get("max_loss_dollars"))
    return (priority, friction, -max_loss)


def _review_summary(review: dict[str, Any]) -> dict[str, Any]:
    small = review.get("small_account_review") or {}
    selected = small.get("selected_contract") or {}
    stock = review.get("stock_setup") or {}
    signals = stock.get("key_signals") or {}
    memory = review.get("setup_memory") or {}
    return {
        "ticker": review.get("ticker"),
        "status": review.get("status"),
        "reason": review.get("reason"),
        "direction": stock.get("direction"),
        "score": stock.get("score"),
        "relative_volume": signals.get("relative_volume"),
        "vwap_state": "above" if signals.get("above_vwap") else "below" if signals.get("below_vwap") else "unknown",
        "priority_score": small.get("priority_score"),
        "friction_adjusted_score": small.get("friction_adjusted_score"),
        "friction_band": small.get("friction_band"),
        "contract": selected.get("contract_symbol"),
        "ask": selected.get("ask"),
        "max_loss_dollars": selected.get("max_loss_dollars"),
        "spread_pct": selected.get("spread_pct"),
        "dte": selected.get("days_to_expiration"),
        "memory_signal": memory.get("memory_signal"),
        "warnings": review.get("warnings") or small.get("warnings") or [],
    }


def _review_followup(review: dict[str, Any]) -> dict[str, Any]:
    stock = review.get("stock_setup") or {}
    quote = stock.get("quote_summary") or {}
    small = review.get("small_account_review") or {}
    selected = small.get("selected_contract") or {}
    direction = str(stock.get("direction") or "").lower()
    return {
        "ticker": review.get("ticker"),
        "direction": direction,
        "entry_reference": quote.get("price"),
        "review_timestamp": quote.get("timestamp") or review.get("timestamp"),
        "contract_symbol": selected.get("contract_symbol"),
        "check_after_minutes": [15, 30, 60],
        "endpoint_template": "/review/outcome?ticker={ticker}&direction={direction}&entry_reference={entry_reference}&review_timestamp={review_timestamp}",
    }


def _float_or_zero(value: Any) -> float:
    try:
        if value is None or value != value:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _review_candidate_for_options(service_container, ticker: str, direction: str, mode: str, max_contract_price: float | None) -> dict:
    symbol = ticker.upper()
    is_scalp = "scalp" in mode.lower()
    scan = service_container.scanner.run_market_scan(mode, [symbol], 1)
    stock_item = (scan["top_candidates"] or scan["pass_list"] or [{}])[0]
    if stock_item.get("status") != "CANDIDATE":
        return service_container.events.log(
            "candidate_options_review",
            {
                "ticker": symbol,
                "status": "NO_TRADE_PLAN",
                "reason": "Stock setup did not clear candidate threshold.",
                "stock_setup": stock_item,
                "options_chain_validation": None,
                "review_only": True,
                "can_place_order_from_this_mcp": False,
            },
        )

    relative_volume = (stock_item.get("key_signals") or {}).get("relative_volume")
    warnings = []
    if is_scalp and relative_volume is not None and relative_volume < service_container.settings.scalp_min_relative_volume:
        warnings.append(
            f"Scalp relative volume {relative_volume} is below the preferred floor "
            f"{service_container.settings.scalp_min_relative_volume}; treat as lower urgency, not an automatic reject."
        )

    effective_max_contract_price = max_contract_price
    if is_scalp and effective_max_contract_price is None:
        effective_max_contract_price = service_container.settings.scalp_max_contract_price
        warnings.append(
            f"Applied small-account scalp max contract price cap: {effective_max_contract_price}."
        )

    options_gate = service_container.options.validate_chain(symbol, direction, effective_max_contract_price)
    small_account_review = _small_account_scalp_review(stock_item, options_gate, mode)
    warnings.extend(small_account_review["warnings"])
    if options_gate.get("status") != "OPTIONS_CHAIN_ACCEPTABLE":
        status = "NO_TRADE_PLAN"
        reason = "Options-chain quality gate failed or returned no acceptable contracts."
    elif is_scalp and small_account_review.get("status") != "SMALL_ACCOUNT_SCALP_ACCEPTABLE":
        status = "NO_TRADE_PLAN"
        reason = "Options chain passed, but small-account scalp gate failed."
    else:
        status = "REVIEW_ONLY_OPTIONS_READY"
        reason = "Stock setup and options-chain quality both passed review gates. Broker review still required."
    payload = {
        "ticker": symbol,
        "status": status,
        "reason": reason,
        "stock_setup": stock_item,
        "options_chain_validation": options_gate,
        "warnings": warnings,
        "max_contract_price_used": effective_max_contract_price,
        "small_account_review": small_account_review,
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "requires_broker_review": True,
        "order_allowed": False,
    }
    payload["setup_memory"] = service_container.setup_memory.compare_snapshot(payload, 100)
    return service_container.events.log("candidate_options_review", payload)


def _small_account_scalp_review(stock_item: dict, options_gate: dict, mode: str) -> dict:
    if "scalp" not in mode.lower():
        return {"profile": "not_scalp", "status": "NOT_APPLICABLE", "priority_score": None, "warnings": []}

    accepted_contracts = options_gate.get("accepted_contracts") or []
    if options_gate.get("status") != "OPTIONS_CHAIN_ACCEPTABLE" or not accepted_contracts:
        return {
            "profile": "small_account_scalp",
            "status": "NO_SMALL_ACCOUNT_CONTRACT",
            "priority_score": 0.0,
            "selected_contract": None,
            "warnings": ["No acceptable small-account contract passed the options-chain gate."],
            "notes": "No selected contract means this candidate must not be ranked above valid contracts.",
        }

    selected = accepted_contracts[0]
    signals = stock_item.get("key_signals") or {}
    stock_score = float(stock_item.get("score") or 0)
    raw_relative_volume = signals.get("relative_volume")
    relative_volume = float(raw_relative_volume) if raw_relative_volume is not None else None
    dte = selected.get("days_to_expiration")
    max_loss = selected.get("max_loss_dollars")
    spread_pct = selected.get("spread_pct")
    bid = selected.get("bid")
    ask = selected.get("ask")
    absolute_spread = round(float(ask) - float(bid), 4) if bid is not None and ask is not None and float(ask) >= float(bid) else None
    friction_review = _friction_adjusted_review(selected)
    direction = str(stock_item.get("direction") or "").lower()
    above_vwap = bool(signals.get("above_vwap"))
    below_vwap = bool(signals.get("below_vwap"))

    warnings: list[str] = []
    hard_failures: list[str] = []
    priority = stock_score
    if relative_volume is None:
        priority -= 6
        warnings.append("Relative volume is unavailable; treat scalp urgency as unconfirmed.")
    elif relative_volume >= 2.0:
        priority += 4
    elif relative_volume < 1.15:
        priority -= 4

    vwap_aligned = (direction == "long" and above_vwap) or (direction == "short" and below_vwap)
    spread_tight_for_1dte = (
        spread_pct is not None and spread_pct <= 0.08
    ) or (
        absolute_spread is not None and absolute_spread <= 0.03
    )

    if dte is not None and dte <= 0:
        priority -= 20
        hard_failures.append("0DTE contracts are blocked for small-account scalp review.")
    elif dte is not None and dte == 1:
        priority -= 8
        warnings.append("Selected contract is 1DTE or less; time decay and whipsaw risk are elevated.")
        exceptional_1dte = stock_score >= 88 and relative_volume is not None and relative_volume >= 1.5 and spread_tight_for_1dte and vwap_aligned
        if not exceptional_1dte:
            hard_failures.append("1DTE requires exceptional stock score, confirmed RVOL, tight spread, and VWAP alignment.")
    elif dte is not None and dte >= 3:
        priority += 3

    if max_loss is not None:
        if max_loss > 100:
            priority -= 12
            warnings.append("Selected contract max loss is above the small-account comfort zone.")
            hard_failures.append("Selected contract max loss is above the small-account cap.")
        elif max_loss <= 50:
            priority += 4

    if spread_pct is not None and spread_pct > 0.08:
        priority -= 10
        warnings.append("Selected contract spread is wider than preferred for a scalp.")
    if spread_pct is not None and spread_pct > 0.15 and (absolute_spread is None or absolute_spread > 0.05):
        hard_failures.append("Selected contract spread is too wide for small-account scalp review.")

    if friction_review["score"] < 55:
        hard_failures.append("Friction-adjusted score is too weak for small-account scalp review.")

    if direction == "long" and below_vwap:
        priority -= 10
        warnings.append("Long direction conflicts with below-VWAP price action.")
        hard_failures.append("Direction conflicts with VWAP alignment.")
    if direction == "short" and above_vwap:
        priority -= 10
        warnings.append("Short direction conflicts with above-VWAP price action.")
        hard_failures.append("Direction conflicts with VWAP alignment.")

    if hard_failures:
        priority = 0.0
    else:
        priority = min(priority, friction_review["score"])

    if warnings:
        priority = min(priority, 95.0)
    if any("1DTE" in warning or "max loss" in warning or "conflicts" in warning for warning in warnings):
        priority = min(priority, 89.0)

    return {
        "profile": "small_account_scalp",
        "status": "SMALL_ACCOUNT_SCALP_ACCEPTABLE" if not hard_failures else "NO_TRADE_PLAN",
        "priority_score": round(max(0.0, min(100.0, priority)), 2),
        "friction_adjusted_score": friction_review["score"],
        "friction_band": friction_review["band"],
        "friction_adjusted_review": friction_review,
        "selected_contract": selected or None,
        "warnings": warnings + hard_failures,
        "notes": "Priority score is for review ordering only; it is not an execution signal.",
    }


def _friction_adjusted_review(contract: dict) -> dict:
    bid = _float_or_none(contract.get("bid"))
    ask = _float_or_none(contract.get("ask"))
    spread_pct = _float_or_none(contract.get("spread_pct"))
    max_loss = _float_or_none(contract.get("max_loss_dollars"))
    dte = _float_or_none(contract.get("days_to_expiration"))
    volume = _float_or_none(contract.get("volume"))
    open_interest = _float_or_none(contract.get("open_interest"))
    absolute_spread = round(ask - bid, 4) if bid is not None and ask is not None and ask >= bid else None
    slippage_dollars = round(absolute_spread * 100, 2) if absolute_spread is not None else None
    slippage_pct_of_max_loss = round(slippage_dollars / max_loss, 4) if slippage_dollars is not None and max_loss and max_loss > 0 else None
    penalties: list[dict[str, Any]] = []

    def add(name: str, penalty: float, reason: str) -> None:
        penalties.append({"name": name, "penalty": penalty, "reason": reason})

    if bid is None or ask is None or ask <= 0 or (bid is not None and ask < bid):
        add("bid_ask_unknown", 8.0, "Bid/ask is missing or invalid, so slippage cannot be trusted.")
    if spread_pct is None:
        add("spread_unknown", 8.0, "Spread percentage is unavailable.")
    elif spread_pct <= 0.05:
        pass
    elif spread_pct <= 0.08:
        add("spread_mild", 4.0, "Spread is acceptable but not ideal for a fast scalp.")
    elif spread_pct <= 0.12:
        add("spread_wide", 10.0, "Spread is wider than preferred and needs limit-order discipline.")
    elif spread_pct <= 0.15:
        add("spread_very_wide", 16.0, "Spread is very wide for a small-account scalp.")
    else:
        add("spread_blocking", 28.0, "Spread is too wide to trust without a much better broker quote.")

    if absolute_spread is not None:
        if absolute_spread > 0.10:
            add("absolute_spread_large", 14.0, "The dollar spread is large enough to create meaningful round-trip friction.")
        elif absolute_spread > 0.05:
            add("absolute_spread_elevated", 8.0, "The dollar spread is elevated for a cheap scalp contract.")
        elif absolute_spread > 0.03:
            add("absolute_spread_noticeable", 4.0, "The dollar spread is noticeable; avoid chasing.")

    if ask is not None and ask <= 0.10 and spread_pct is not None and spread_pct > 0.08:
        add("cheap_contract_tick_risk", 4.0, "Very cheap contracts can have misleading percentage spreads and fast premium decay.")

    if volume is None:
        add("volume_unknown", 4.0, "Contract volume is unavailable.")
    elif volume < 50:
        add("volume_thin", 12.0, "Contract volume is thin for clean entry/exit.")
    elif volume < 250:
        add("volume_light", 6.0, "Contract volume is usable but lighter than preferred.")
    elif volume < 1000:
        add("volume_ok_not_deep", 2.0, "Contract volume is acceptable but not deep.")

    if open_interest is None:
        add("open_interest_unknown", 4.0, "Open interest is unavailable.")
    elif open_interest < 50:
        add("open_interest_thin", 12.0, "Open interest is too thin for reliable small-account review.")
    elif open_interest < 250:
        add("open_interest_light", 6.0, "Open interest is usable but lighter than preferred.")
    elif open_interest < 1000:
        add("open_interest_ok_not_deep", 2.0, "Open interest is acceptable but not deep.")

    if dte is None:
        add("dte_unknown", 6.0, "DTE is unavailable.")
    elif dte <= 0:
        add("zero_dte_blocked", 100.0, "0DTE is blocked for this review profile.")
    elif dte == 1:
        add("one_dte_decay", 12.0, "1DTE has elevated time-decay and whipsaw risk.")
    elif dte == 2:
        add("two_dte_caution", 4.0, "2DTE is workable but still decay-sensitive.")
    elif dte > 14:
        add("too_much_duration_for_scalp", 4.0, "Longer-dated contract may be less efficient for the intended scalp profile.")

    if max_loss is None:
        add("max_loss_unknown", 10.0, "Max loss is unavailable.")
    elif max_loss <= 25:
        pass
    elif max_loss <= 50:
        add("max_loss_mild", 2.0, "Max loss is still small-account friendly but no longer tiny.")
    elif max_loss <= 75:
        add("max_loss_elevated", 6.0, "Max loss is elevated for a tiny test account.")
    elif max_loss <= 100:
        add("max_loss_high", 10.0, "Max loss is high for a small-account scalp.")
    else:
        add("max_loss_blocking", 22.0, "Max loss is above the small-account comfort zone.")

    score = round(max(0.0, min(100.0, 100.0 - sum(item["penalty"] for item in penalties))), 2)
    band = "LOW_FRICTION" if score >= 85 else "MANAGEABLE_FRICTION" if score >= 70 else "HIGH_FRICTION" if score >= 55 else "BLOCKED_BY_FRICTION"
    return {
        "score": score,
        "band": band,
        "penalties": penalties,
        "components": {
            "bid": bid,
            "ask": ask,
            "spread_pct": spread_pct,
            "absolute_spread": absolute_spread,
            "estimated_round_trip_slippage_dollars": slippage_dollars,
            "slippage_pct_of_max_loss": slippage_pct_of_max_loss,
            "volume": volume,
            "open_interest": open_interest,
            "days_to_expiration": dte,
            "max_loss_dollars": max_loss,
        },
        "notes": [
            "Friction-adjusted score is a review-quality filter, not an execution signal.",
            "Limit orders remain required; no market order path exists in this MCP.",
        ],
    }


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None or value != value:
            return None
        return float(value)
    except Exception:
        return None


@mcp.tool
def generate_trade_plan(ticker: str, direction: str, setup_type: str, account_value: float, max_risk_dollars: float | None = None, is_options_trade: bool = False, is_zero_dte: bool = False, order_type: str = "limit", notes: str = "") -> dict:
    settings = container.settings
    risk = max_risk_dollars if max_risk_dollars is not None else round(account_value * settings.max_trade_risk_pct, 2)
    if is_options_trade:
        options_gate = container.options.validate_chain(ticker, direction, None)
        if options_gate.get("status") != "OPTIONS_CHAIN_ACCEPTABLE":
            return container.events.log(
                "trade_plan",
                {
                    "ticker": ticker.upper(),
                    "status": "NO_TRADE_PLAN",
                    "reason": "Options-chain quality gate failed.",
                    "options_chain_validation": options_gate,
                    "review_only": True,
                    "can_place_order_from_this_mcp": False,
                    "requires_broker_review": True,
                },
            )
    plan = {"ticker": ticker.upper(), "direction": direction, "setup_type": setup_type, "account_value": account_value, "proposed_risk_dollars": risk, "is_options_trade": is_options_trade, "is_zero_dte": is_zero_dte, "order_type": order_type, "review_only": True, "can_place_order_from_this_mcp": False, "requires_broker_review": True, "manual_approval_required": True, "approval_phrase_required": settings.approval_phrase, "notes": notes}
    return container.events.log("trade_plan", plan)


@mcp.tool
def check_risk_limits(trade_plan: dict[str, Any]) -> dict:
    plan = TradePlan(
        ticker=trade_plan["ticker"],
        direction=Direction(trade_plan.get("direction", "long")),
        setup_type=trade_plan.get("setup_type", "day_trade"),
        account_value=float(trade_plan.get("account_value", 0)),
        proposed_risk_dollars=float(trade_plan.get("proposed_risk_dollars", trade_plan.get("max_risk_dollars", 0))),
        order_type=OrderType(trade_plan.get("order_type", "limit")),
        is_options_trade=bool(trade_plan.get("is_options_trade", False)),
        is_zero_dte=bool(trade_plan.get("is_zero_dte", False)),
        requested_execution=bool(trade_plan.get("requested_execution", False)),
        approval_text=trade_plan.get("approval_text"),
    )
    return container.risk.check(plan)


@mcp.tool
def log_trade_decision(decision: dict[str, Any]) -> dict:
    return container.journal.log_trade_decision(decision)


@mcp.tool
def log_trade_result(result: dict[str, Any]) -> dict:
    return container.journal.log_trade_result(result)


@mcp.tool
def log_review_decision(decision: dict[str, Any]) -> dict:
    return container.review_outcomes.log_review_decision(decision)


@mcp.tool
def check_review_outcome(review: dict[str, Any], horizons: dict[str, int] | None = None) -> dict:
    return container.review_outcomes.check_review_outcome(review, horizons)


@mcp.tool
def summarize_review_outcomes(outcomes: list[dict[str, Any]]) -> dict:
    return container.review_outcomes.summarize_review_outcomes(outcomes)


@mcp.tool
def log_research_snapshot(snapshot: dict[str, Any]) -> dict:
    return container.learning.log_research_snapshot(snapshot)


@mcp.tool
def classify_review_outcome(snapshot: dict[str, Any], outcome: dict[str, Any], help_threshold: float = 0.003, missed_move_threshold: float = 0.006) -> dict:
    return container.learning.classify_review_outcome(snapshot, outcome, help_threshold, missed_move_threshold)


@mcp.tool
def summarize_learning(classifications: list[dict[str, Any]] | None = None, limit: int = 100) -> dict:
    return container.learning.summarize_learning(classifications, limit)


@mcp.tool
def generate_learning_rule_proposals(classifications: list[dict[str, Any]] | None = None, min_samples: int = 3, limit: int = 100) -> dict:
    return container.learning.generate_rule_proposals(classifications, min_samples, limit)


@mcp.tool
def run_postmortem(date: str | None = None) -> dict:
    return container.postmortem.run_postmortem(date)


@mcp.tool
def run_backtest(engine: str, tickers: list[str], start: str, end: str, config_overrides: dict | None = None) -> dict:
    overrides = config_overrides or {}
    lowered = engine.lower()
    if "crypto" in lowered and "paper" in lowered:
        rule_overrides = {
            key: value
            for key, value in overrides.items()
            if key not in {"period", "interval", "starting_cash", "max_trades_per_symbol"}
        }
        return container.crypto_paper.run_backtest(
            symbols=tickers,
            period=str(overrides.get("period", "1d")),
            interval=str(overrides.get("interval", "5m")),
            starting_cash=float(overrides.get("starting_cash", 5.0)),
            max_trades_per_symbol=int(overrides.get("max_trades_per_symbol", 50)),
            rule_overrides=rule_overrides,
        )
    return container.backtest.run_backtest(engine, tickers, start, end, config_overrides)


@mcp.tool
def get_crypto_paper_rules() -> dict:
    rules = container.crypto_paper.rules()
    return {
        "mode": "crypto_paper_only",
        "rules": rules.__dict__,
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "notes": "Crypto paper tools simulate and log only. They do not call Robinhood and cannot place broker orders.",
    }


@mcp.tool
def start_crypto_paper_session(starting_cash: float = 5.0, symbols: list[str] | None = None, duration_hours: int = 8, interval_minutes: int = 15) -> dict:
    return container.crypto_paper.start_session(starting_cash, symbols, duration_hours, interval_minutes)


@mcp.tool
def run_crypto_paper_backtest(symbols: list[str] | None = None, period: str = "1d", interval: str = "5m", starting_cash: float = 5.0, max_trades_per_symbol: int = 50) -> dict:
    return container.crypto_paper.run_backtest(symbols, period, interval, starting_cash, max_trades_per_symbol)


@mcp.tool
def get_offhours_research_plan() -> dict:
    return container.global_research.offhours_plan()


@mcp.tool
def run_global_research_scan(market: str = "global", symbols: list[str] | None = None, period: str = "5d", interval: str = "5m", max_candidates: int = 20) -> dict:
    return container.global_research.run_global_research_scan(market, symbols, period, interval, max_candidates)


@mcp.tool
def get_trading_monster_blueprint() -> dict:
    return container.premove_blueprint.blueprint()


@mcp.tool
def get_feature_registry() -> dict:
    return container.premove_blueprint.feature_registry()


@mcp.tool
def get_scoring_model() -> dict:
    return container.premove_blueprint.scoring_model()


@mcp.tool
def explain_premove_score(snapshot: dict[str, Any]) -> dict:
    return container.premove_blueprint.explain_candidate_score(snapshot)


@mcp.tool
def build_evidence_packet(item: dict[str, Any], source: str = "manual") -> dict:
    return container.evidence_packets.build_packet(item, source)


@mcp.tool
def build_evidence_packets_from_scan(scan_result: dict[str, Any], source: str = "scan_result") -> dict:
    return container.evidence_packets.build_packets_from_scan(scan_result, source)


@mcp.tool
def summarize_evidence_packets(packets: list[dict[str, Any]] | None = None, limit: int = 100) -> dict:
    return container.evidence_packets.summarize_packets(packets, limit)


@mcp.tool
def generate_updated_prompt() -> dict:
    return container.prompt.generate_updated_prompt()


@mcp.tool
def get_safety_config() -> dict:
    settings = container.settings
    return {"review_only": True, "place_orders": False, "market_orders_allowed": False, "manual_approval_required": settings.manual_approval_required, "approval_phrase": settings.approval_phrase, "automation_flags_inert": True, "pending_buy_recheck_seconds": settings.pending_buy_recheck_seconds, "can_place_order_from_this_mcp": False, "can_cancel_order_from_this_mcp": False}


@mcp.tool
def get_daily_status(account_value: float = 0, day_start_value: float = 0) -> dict:
    return container.risk.daily_status(account_value, day_start_value)


@mcp.tool
def get_watchlist() -> dict:
    return container.scanner.watchlist()


@mcp.tool
def explain_last_recommendation() -> dict:
    return {"summary": "Recommendations are logged in SQLite. PASS remains valid whenever edge, data, liquidity, or regime quality is unclear."}


if __name__ == "__main__":
    mcp.run()
