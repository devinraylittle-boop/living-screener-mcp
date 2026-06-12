from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

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
        "does not store broker credentials, and does not call broker APIs. For options review, use "
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
        "options_data_provider": settings.options_data_provider,
        "options_truth_status": container.options.options_data_status()["real_money_options_truth_status"],
        "has_finnhub_api_key": bool(settings.finnhub_api_key),
        "has_marketdata_api_key": bool(settings.marketdata_api_key),
        "has_tradier_access_token": bool(settings.tradier_access_token),
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
    }


def _resolve_universe(service_container, tickers: list[str] | None) -> list[str]:
    settings = service_container.settings
    configured = (
        tickers
        or getattr(settings, "default_tickers", None)
        or getattr(settings, "scalp_watchlist", None)
        or getattr(settings, "default_watchlist", ())
    )
    return [str(ticker).upper().strip() for ticker in configured if str(ticker).strip()]


@mcp.tool
def run_market_scan(mode: str, tickers: list[str] | None = None, max_candidates: int = 25) -> dict:
    return container.scanner.run_market_scan(mode, tickers, max_candidates)


@mcp.tool
def run_scalp_scan(tickers: list[str] | None = None, max_candidates: int = 25) -> dict:
    return container.scanner.run_market_scan("scalp_review", tickers, max_candidates)


@mcp.tool
def get_event_volatility_playbook(event_name: str = "spacex_ipo", account_value: float = 50.0) -> dict:
    return _get_event_volatility_playbook(container, event_name, account_value)


@mcp.tool
def get_event_radar() -> dict:
    return _get_event_radar(container)


@mcp.tool
def run_event_volatility_scan(
    event_name: str = "spacex_ipo",
    tickers: list[str] | None = None,
    max_candidates: int = 25,
    account_value: float = 50.0,
    review_top_n: int = 8,
    max_contract_price: float | None = None,
) -> dict:
    return _run_event_volatility_scan(container, event_name, tickers, max_candidates, account_value, review_top_n, max_contract_price)


@mcp.tool
def run_broad_opportunity_scan(
    tickers: list[str] | None = None,
    max_candidates: int = 25,
    account_value: float = 50.0,
    review_top_n: int = 10,
    max_contract_price: float | None = None,
    include_event_context: bool = True,
) -> dict:
    return _run_broad_opportunity_scan(container, tickers, max_candidates, account_value, review_top_n, max_contract_price, include_event_context)


@mcp.tool
def get_data_truth_cockpit(tickers: list[str] | None = None, max_tickers: int = 12) -> dict:
    return _get_data_truth_cockpit(container, tickers, max_tickers)


@mcp.tool
def get_system_communication_audit() -> dict:
    return _get_system_communication_audit(container)


@mcp.tool
def get_strategy_module_registry() -> dict:
    return _get_strategy_module_registry(container)


@mcp.tool
def get_shared_intelligence_layer(tickers: list[str] | None = None, limit_events: int = 100) -> dict:
    return _get_shared_intelligence_layer(container, tickers, limit_events)


@mcp.tool
def get_autonomous_launch_decision(account_value: float = 100.0, intended_cash: float = 100.0, tickers: list[str] | None = None) -> dict:
    return _get_autonomous_launch_decision(container, account_value, intended_cash, tickers)


@mcp.tool
def get_real_cash_proof_gate(
    account_value: float = 100.0,
    intended_cash: float = 100.0,
    tickers: list[str] | None = None,
    broker_account_confirmed: bool = False,
    buying_power_confirmed: bool = False,
    open_orders_checked: bool = False,
    open_positions_checked: bool = False,
    no_duplicate_order_confirmed: bool = False,
    order_preview_confirmed: bool = False,
    options_snapshot_validated: bool = False,
    separate_broker_executor_proven: bool = False,
) -> dict:
    return _get_real_cash_proof_gate(
        container,
        account_value,
        intended_cash,
        tickers,
        broker_account_confirmed,
        buying_power_confirmed,
        open_orders_checked,
        open_positions_checked,
        no_duplicate_order_confirmed,
        order_preview_confirmed,
        options_snapshot_validated,
        separate_broker_executor_proven,
    )


@mcp.tool
def get_broker_proof_bridge(
    account_value: float = 100.0,
    intended_cash: float = 100.0,
    ticker: str = "",
    contract_symbol: str = "",
    account_last4: str = "",
    account_type: str = "",
    broker_account_confirmed: bool = False,
    buying_power_confirmed: bool = False,
    buying_power: float | None = None,
    open_orders_checked: bool = False,
    open_order_count: int | None = None,
    open_positions_checked: bool = False,
    open_position_count: int | None = None,
    duplicate_order_active: bool = False,
    order_preview_confirmed: bool = False,
    preview_order_type: str = "limit",
    preview_side: str = "buy",
    preview_quantity: int = 1,
    preview_limit_price: float | None = None,
    preview_max_loss: float | None = None,
    options_snapshot_validated: bool = False,
    options_snapshot_age_seconds: float | None = None,
    broker_source: str = "operator_supplied",
    separate_broker_executor_proven: bool = False,
) -> dict:
    return _get_broker_proof_bridge(
        container,
        account_value,
        intended_cash,
        ticker,
        contract_symbol,
        account_last4,
        account_type,
        broker_account_confirmed,
        buying_power_confirmed,
        buying_power,
        open_orders_checked,
        open_order_count,
        open_positions_checked,
        open_position_count,
        duplicate_order_active,
        order_preview_confirmed,
        preview_order_type,
        preview_side,
        preview_quantity,
        preview_limit_price,
        preview_max_loss,
        options_snapshot_validated,
        options_snapshot_age_seconds,
        broker_source,
        separate_broker_executor_proven,
    )


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
def get_trading_day_launch_checklist(tickers: list[str] | None = None, account_value: float = 50.0, max_candidates: int = 25) -> dict:
    return _get_trading_day_launch_checklist(container, tickers, account_value, max_candidates)


@mcp.tool
def get_tomorrow_operator_brief(tickers: list[str] | None = None, account_value: float = 50.0, max_candidates: int = 25) -> dict:
    return _get_tomorrow_operator_brief(container, tickers, account_value, max_candidates)


@mcp.tool
def run_go_live_rehearsal(tickers: list[str] | None = None, account_value: float = 50.0, max_candidates: int = 25, include_market_check: bool = False) -> dict:
    return _run_go_live_rehearsal(container, tickers, account_value, max_candidates, include_market_check)


@mcp.tool
def run_trading_day_heartbeat(
    tickers: list[str] | None = None,
    account_value: float = 50.0,
    max_candidates: int = 25,
    review_top_n: int = 8,
    max_contract_price: float | None = None,
    force_phase: str | None = None,
) -> dict:
    return _run_trading_day_heartbeat(container, tickers, account_value, max_candidates, review_top_n, max_contract_price, force_phase)


@mcp.tool
def summarize_trading_day_alerts(limit: int = 50) -> dict:
    return _summarize_trading_day_alerts(container, limit)


@mcp.tool
def run_morning_readiness_autopilot(tickers: list[str] | None = None, account_value: float = 50.0, max_candidates: int = 25) -> dict:
    return _run_morning_readiness_autopilot(container, tickers, account_value, max_candidates)


@mcp.tool
def run_autonomous_morning_scan(
    tickers: list[str] | None = None,
    account_value: float = 50.0,
    max_candidates: int = 25,
    review_top_n: int = 8,
    max_contract_price: float | None = None,
    force_phase: str | None = None,
    catalyst_top_n: int = 5,
) -> dict:
    return _run_autonomous_morning_scan(
        container,
        tickers,
        account_value,
        max_candidates,
        review_top_n,
        max_contract_price,
        force_phase,
        catalyst_top_n,
    )


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
def run_market_open_observer(tickers: list[str] | None = None, max_candidates: int = 25, cadence_minutes: int = 5) -> dict:
    return _run_market_open_observer(container, tickers, max_candidates, cadence_minutes)


@mcp.tool
def run_observer_followup(limit_observations: int = 3, max_items: int = 20, include_passes: bool = True, classify: bool = True) -> dict:
    return _run_observer_followup(container, limit_observations, max_items, include_passes, classify)


@mcp.tool
def analyze_ticker(ticker: str, mode: str | None = None) -> dict:
    return container.scanner.analyze_ticker(ticker, mode)


@mcp.tool
def validate_options_chain(ticker: str, direction: str = "call", max_contract_price: float | None = None) -> dict:
    return container.options.validate_chain(ticker, direction, max_contract_price)


@mcp.tool
def get_options_data_status() -> dict:
    return container.options.options_data_status()


@mcp.tool
def get_truth_source_status() -> dict:
    return container.market_truth.truth_source_status()


@mcp.tool
def check_market_data_health(tickers: list[str] | None = None, max_tickers: int = 10) -> dict:
    return container.market_truth.check_market_data_health(tickers, max_tickers)


@mcp.tool
def get_catalyst_context(ticker: str, lookback_days: int = 3, lookahead_days: int = 7) -> dict:
    return container.market_truth.get_catalyst_context(ticker, lookback_days, lookahead_days)


@mcp.tool
def validate_broker_option_snapshot(snapshot: dict[str, Any], max_contract_price: float | None = None) -> dict:
    return container.options.validate_broker_snapshot(snapshot, max_contract_price)


@mcp.tool
def build_manual_trade_preflight_ticket(snapshot: dict[str, Any], account_value: float = 50.0, max_contract_price: float | None = None, notes: str = "") -> dict:
    return _build_manual_trade_preflight_ticket(container, snapshot, account_value, max_contract_price, notes)


@mcp.tool
def build_manual_trade_desk(
    snapshot: dict[str, Any],
    account_value: float = 50.0,
    max_contract_price: float | None = None,
    notes: str = "",
    max_open_positions: int = 2,
) -> dict:
    return _build_manual_trade_desk(container, snapshot, account_value, max_contract_price, notes, max_open_positions)


@mcp.tool
def log_manual_broker_action(action: dict[str, Any]) -> dict:
    return _log_manual_broker_action(container, action)


@mcp.tool
def log_manual_option_paper_entry(ticket: dict[str, Any], fill_price: float, quantity: int = 1, underlying_price: float | None = None, notes: str = "") -> dict:
    return _log_manual_option_paper_entry(container, ticket, fill_price, quantity, underlying_price, notes)


@mcp.tool
def run_paper_exploration(
    tickers: list[str] | None = None,
    max_candidates: int = 50,
    max_trials: int = 20,
    max_contract_price: float | None = None,
    include_passes: bool = True,
    exploration_level: str = "aggressive",
) -> dict:
    return _run_paper_exploration(container, tickers, max_candidates, max_trials, max_contract_price, include_passes, exploration_level)


@mcp.tool
def run_paper_exploration_followup(limit_runs: int = 5, max_items: int = 80, classify: bool = True) -> dict:
    return _run_paper_exploration_followup(container, limit_runs, max_items, classify)


@mcp.tool
def close_manual_option_paper_trade(entry_id: int | None = None, contract_symbol: str | None = None, exit_price: float = 0.0, exit_reason: str = "manual_close", notes: str = "") -> dict:
    return _close_manual_option_paper_trade(container, entry_id, contract_symbol, exit_price, exit_reason, notes)


@mcp.tool
def watch_manual_option_position(
    entry_id: int | None = None,
    contract_symbol: str | None = None,
    current_bid: float | None = None,
    current_ask: float | None = None,
    current_mark: float | None = None,
    underlying_price: float | None = None,
    underlying_vwap: float | None = None,
    notes: str = "",
) -> dict:
    return _watch_manual_option_position(container, entry_id, contract_symbol, current_bid, current_ask, current_mark, underlying_price, underlying_vwap, notes)


@mcp.tool
def get_session_risk_guard(account_value: float = 50.0, proposed_risk_dollars: float | None = None, max_open_positions: int = 2) -> dict:
    return _get_session_risk_guard(container, account_value, proposed_risk_dollars, max_open_positions)


@mcp.tool
def get_failure_mode_audit() -> dict:
    return _get_failure_mode_audit(container)


@mcp.tool
def summarize_manual_option_paper_trades(limit: int = 100) -> dict:
    return _summarize_manual_option_paper_trades(container, limit)


@mcp.tool
def summarize_paper_exploration(limit: int = 100) -> dict:
    return _summarize_paper_exploration(container, limit)


@mcp.tool
def export_journal_checkpoint(limit: int = 500, event_types: list[str] | None = None) -> dict:
    return _export_journal_checkpoint(container, limit, event_types)


@mcp.tool
def restore_journal_checkpoint(checkpoint: dict[str, Any], source_label: str = "manual_restore", max_events: int = 500) -> dict:
    return _restore_journal_checkpoint(container, checkpoint, source_label, max_events)


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


def _event_volatility_universe(service_container, tickers: list[str] | None) -> list[str]:
    configured = tickers or list(getattr(service_container.settings, "event_volatility_watchlist", ()))
    seen: set[str] = set()
    universe: list[str] = []
    for ticker in configured:
        symbol = str(ticker or "").upper().strip()
        if symbol and symbol not in seen:
            seen.add(symbol)
            universe.append(symbol)
    return universe


def _broad_opportunity_universe(service_container, tickers: list[str] | None, include_event_context: bool = True) -> list[str]:
    settings = service_container.settings
    configured: list[str] = []
    configured.extend(list(getattr(settings, "broad_opportunity_watchlist", ())))
    configured.extend(list(getattr(settings, "scalp_watchlist", ())))
    if include_event_context:
        configured.extend(list(getattr(settings, "event_volatility_watchlist", ())))
    if tickers:
        configured.extend([str(ticker).upper().strip() for ticker in tickers])
    seen: set[str] = set()
    universe: list[str] = []
    max_universe = max(10, int(getattr(settings, "max_scan_universe", 75) or 75))
    for ticker in configured:
        symbol = str(ticker or "").upper().strip()
        if not symbol or symbol in seen or "-" in symbol:
            continue
        seen.add(symbol)
        universe.append(symbol)
        if len(universe) >= max_universe:
            break
    return universe


def _get_event_radar(service_container) -> dict:
    settings = service_container.settings
    event_watchlist = list(getattr(settings, "event_volatility_watchlist", ()))
    broad_watchlist = list(getattr(settings, "broad_opportunity_watchlist", ()))
    payload = {
        "status": "EVENT_RADAR_READY",
        "build_version": BUILD_VERSION,
        "generated_at": utc_now(),
        "mission": "Keep catalysts on radar without letting any single story create tunnel vision.",
        "active_events": [
            {
                "event_id": "spacex_ipo_2026_06_12",
                "label": "SpaceX IPO / SPCX expected listing",
                "expected_date": "2026-06-12",
                "confidence": "operator_research_pending_final_exchange_verification",
                "direct_symbol": settings.event_direct_symbol,
                "event_type": "ipo",
                "primary_risk": "Fresh IPO volatility, uncertain opening mechanics, and likely no direct listed options at launch.",
                "watchlist": event_watchlist,
                "playbook_link": "/ops/event-volatility-playbook?event_name=spacex_ipo&format=html",
                "scan_link": "/ops/event-volatility-scan?event_name=spacex_ipo&format=html",
                "rule": "Use as context, not as a mandate. Broad market scan remains required.",
            }
        ],
        "radar_lanes": [
            {
                "lane": "scheduled_events",
                "examples": ["IPOs", "earnings", "Fed/CPI/PPI/jobs", "major product launches", "regulatory rulings"],
                "current_status": "Manual/operator-fed until a trusted news/calendar feed is configured.",
            },
            {
                "lane": "live_market_discovery",
                "examples": ["relative volume spikes", "VWAP breaks", "sector sympathy", "index volatility"],
                "current_status": "Handled by run_broad_opportunity_scan and normal scalp scans.",
            },
            {
                "lane": "microcap_research",
                "examples": list(getattr(settings, "microcap_research_watchlist", ())),
                "current_status": "Paper/research only by default; do not mix into real-cash options ranking.",
            },
            {
                "lane": "crypto_research",
                "examples": list(getattr(settings, "crypto_research_symbols", ())),
                "current_status": "Separate paper/backtest lane; do not blend with equity/options scoring.",
            },
        ],
        "anti_tunnel_vision_rules": [
            "Run broad opportunity scan even when an event is active.",
            "Do not allocate every review slot to event-related names.",
            "Prefer an unrelated clean setup over an event-adjacent messy setup.",
            "Report event-related and non-event candidate counts separately.",
            "Treat event watchlists as context, not prediction.",
        ],
        "broad_market_universe_preview": broad_watchlist[:75],
        "links": {
            "broad_opportunity_scan": "/ops/broad-opportunity-scan?format=html",
            "event_playbook": "/ops/event-volatility-playbook?format=html",
            "event_scan": "/ops/event-volatility-scan?format=html",
            "crypto_rules": "/crypto/rules",
            "crypto_backtest": "/crypto/backtest",
        },
        "safety": {
            "review_only": True,
            "place_orders": False,
            "market_orders_allowed": False,
            "paper_research_uncapped": True,
            "real_cash_daily_closed_loss_lockout_count": settings.max_daily_real_cash_closed_losses,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        },
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
    }
    return service_container.events.log("event_radar", payload)


def _get_event_volatility_playbook(service_container, event_name: str, account_value: float) -> dict:
    settings = service_container.settings
    event_key = (event_name or settings.event_theme or "event_volatility").strip().lower()
    universe = _event_volatility_universe(service_container, None)
    direct_symbol = str(settings.event_direct_symbol or "SPCX").upper()
    account_value = _float_or_zero(account_value) or 50.0
    contract_cap = settings.scalp_max_contract_price
    payload = {
        "status": "EVENT_VOLATILITY_PLAYBOOK_READY",
        "build_version": BUILD_VERSION,
        "event_name": event_key,
        "generated_at": utc_now(),
        "mission": "Exploit event-driven volatility only when data, direction, spread, and sizing gates agree.",
        "direct_symbol": direct_symbol,
        "universe": universe,
        "account_value_reference": account_value,
        "small_account_contract_cap": contract_cap,
        "stock_lane_allowed": True,
        "options_lane_allowed_only_after": [
            "VALID_CANDIDATE stock setup",
            "Clear direction",
            "OPTIONS_CHAIN_ACCEPTABLE",
            "SMALL_ACCOUNT_SCALP_ACCEPTABLE",
            "Manual broker snapshot/preflight for real money",
        ],
        "lanes": [
            {
                "lane": "DIRECT_IPO_STOCK_REVIEW",
                "applies_to": [direct_symbol],
                "allowed_in_mcp": "review_only",
                "rule": "Treat the fresh listing as stock-only review until listed options exist and a broker-visible snapshot proves live bid/ask, volume, open interest, and max loss.",
                "do_not_do": "Do not assume same-day direct options exist; do not synthesize an option chain from stale or related-symbol data.",
            },
            {
                "lane": "SYMPATHY_OPTIONS_REVIEW",
                "applies_to": [ticker for ticker in universe if ticker != direct_symbol and not ticker.endswith(("X", "A"))],
                "allowed_in_mcp": "review_only",
                "rule": "Only review options after a valid directional stock setup. Rank only REVIEW_ONLY_OPTIONS_READY plus SMALL_ACCOUNT_SCALP_ACCEPTABLE.",
                "do_not_do": "Do not rank OPTIONS_CHAIN_ACCEPTABLE alone, and do not rank stock setup alone as an options idea.",
            },
            {
                "lane": "INDEX_VOLATILITY_REVIEW",
                "applies_to": ["SPY", "QQQ", "IWM"],
                "allowed_in_mcp": "review_only",
                "rule": "Use indexes as cleaner volatility/liquidity proxies when single-name sympathy chains are wide, stale, or too expensive.",
                "do_not_do": "Do not force 0DTE. Prefer no trade over decay exposure without fresh options truth.",
            },
            {
                "lane": "STOCK_REVIEW_FALLBACK",
                "applies_to": "Any valid stock setup whose options truth is missing, expensive, wide, or illiquid.",
                "allowed_in_mcp": "review_only",
                "rule": "Allow stock review when options are unavailable or inferior. This is a separate lane, not an options downgrade.",
                "do_not_do": "Do not convert stock review into an option trade without fresh contract proof.",
            },
        ],
        "hard_no_trade_gates": [
            "Wrong build or failed safety config.",
            "Regular-session quote/candle health is stale, missing, or derived from a weak proxy.",
            "No clear direction or VWAP conflict.",
            "Options spread, quote age, volume, open interest, DTE, or max loss fails the small-account gate.",
            "Real-cash closed loss count reaches 3 for the day.",
            "Manual broker snapshot is unavailable for real-money options truth.",
        ],
        "tomorrow_timeline_central": [
            {"time": "07:30-08:25", "action": "Premarket observe only; collect catalysts, gaps, and sympathy leaders."},
            {"time": "08:30-08:45", "action": "Opening noise window. Run observer; avoid ranking contracts unless data quality is excellent."},
            {"time": "08:45-10:30", "action": "Primary review window. Run event scan, then options review only for valid directional candidates."},
            {"time": "10:30-13:30", "action": "Selective continuation or reversal review. Prefer fewer, cleaner setups."},
            {"time": "13:30-close", "action": "Reduce 0DTE appetite. Only review if momentum, spread, and liquidity are exceptional."},
        ],
        "stock_vs_options_decision": [
            "Prefer options when stock setup is strong, contract is liquid, spread is tight, DTE/max loss fit account size, and broker snapshot confirms truth.",
            "Prefer stock when direct IPO options are unavailable, contract spreads are too wide, IV/theta risk is hostile, or a swing idea is cleaner than a scalp.",
            "Prefer no trade when both lanes require assumptions.",
        ],
        "links": {
            "playbook": "/ops/event-volatility-playbook?format=html",
            "event_scan": "/ops/event-volatility-scan?format=html",
            "market_open_observer": f"/ops/market-open-observer?tickers={','.join(universe)}&max_candidates=25&format=html",
            "live_review_cycle": f"/ops/live-review-cycle?tickers={','.join(universe)}&account_value={account_value}&max_candidates=25&review_top_n=8&max_contract_price={contract_cap}&format=html",
            "manual_preflight": "/review/manual-preflight?format=html",
        },
        "safety": {
            "review_only": True,
            "place_orders": False,
            "market_orders_allowed": False,
            "manual_approval_required": True,
            "paper_research_uncapped": True,
            "real_cash_daily_closed_loss_lockout_count": settings.max_daily_real_cash_closed_losses,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        },
        "notes": [
            "This is an event-day decision map, not a prediction and not a broker action.",
            "The machine should become more active in paper/research, not more reckless with real cash.",
            "Every accepted candidate still needs live truth, manual preflight, and post-outcome learning.",
        ],
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
    }
    return service_container.events.log("event_volatility_playbook", payload)


def _run_event_volatility_scan(
    service_container,
    event_name: str,
    tickers: list[str] | None,
    max_candidates: int,
    account_value: float,
    review_top_n: int,
    max_contract_price: float | None,
) -> dict:
    max_candidates = max(1, min(int(max_candidates or 25), 50))
    review_top_n = max(1, min(int(review_top_n or 8), 20))
    universe = _event_volatility_universe(service_container, tickers)
    direct_symbol = str(service_container.settings.event_direct_symbol or "SPCX").upper()
    event_key = (event_name or service_container.settings.event_theme or "event_volatility").strip().lower()
    effective_contract_cap = max_contract_price
    if effective_contract_cap is None:
        effective_contract_cap = service_container.settings.scalp_max_contract_price
    scan = service_container.scanner.run_market_scan("scalp_review", universe, max_candidates)
    top_rows = list(scan.get("top_candidates") or [])
    pass_rows = list(scan.get("pass_list") or [])
    stock_candidates = [
        row
        for row in top_rows
        if row.get("status") == "CANDIDATE"
        and (row.get("quality_gates") or {}).get("stock_setup_quality") == "VALID_CANDIDATE"
        and str(row.get("direction") or "").lower() in {"long", "short"}
    ]
    reviews: dict[str, dict[str, Any]] = {}
    for candidate in stock_candidates[:review_top_n]:
        ticker = str(candidate.get("ticker") or "").upper()
        if ticker == direct_symbol:
            continue
        direction = str(candidate.get("direction") or "").lower()
        option_direction = "call" if direction == "long" else "put"
        reviews[ticker] = _review_candidate_for_options(
            service_container,
            ticker,
            option_direction,
            "scalp_review",
            effective_contract_cap,
        )

    lane_decisions = [
        _event_lane_decision(row, reviews.get(str(row.get("ticker") or "").upper()), direct_symbol)
        for row in stock_candidates
    ]
    ranked_options = [
        decision
        for decision in lane_decisions
        if decision.get("lane") == "SYMPATHY_OPTIONS_REVIEW_READY"
    ]
    ranked_options.sort(
        key=lambda item: (
            _float_or_zero(item.get("priority_score")),
            _float_or_zero(item.get("friction_adjusted_score")),
            -_float_or_zero(item.get("max_loss_dollars")),
        ),
        reverse=True,
    )
    stock_review = [
        decision
        for decision in lane_decisions
        if decision.get("lane") in {"DIRECT_IPO_STOCK_REVIEW", "STOCK_REVIEW_FALLBACK", "INDEX_VOLATILITY_STOCK_REVIEW"}
    ]
    direct_present = any(str(row.get("ticker") or "").upper() == direct_symbol for row in top_rows + pass_rows)
    status = "EVENT_OPTIONS_READY" if ranked_options else "EVENT_STOCK_REVIEW_ONLY" if stock_review else "EVENT_NO_TRADE_PLAN"
    next_action = (
        "Review ranked options only after manual broker snapshot/preflight."
        if ranked_options
        else "Track stock lanes and rerun; do not force options until the contract gate passes."
        if stock_review
        else "Keep observing. No event-lane candidate cleared the stock setup gate."
    )
    payload = {
        "status": status,
        "build_version": BUILD_VERSION,
        "event_name": event_key,
        "generated_at": utc_now(),
        "universe": universe,
        "direct_symbol": direct_symbol,
        "direct_symbol_status": "SCANNED_OR_PRESENT" if direct_present else "NOT_RETURNED_BY_DATA_PROVIDER_YET",
        "account_value_reference": _float_or_zero(account_value) or 50.0,
        "max_candidates": max_candidates,
        "review_top_n": review_top_n,
        "max_contract_price_used": effective_contract_cap,
        "scan_summary": _scan_summary(scan),
        "stock_candidate_count": len(stock_candidates),
        "options_review_count": len(reviews),
        "ranked_options_candidates": ranked_options,
        "stock_review_candidates": stock_review,
        "watch_only_or_rejected": [
            decision for decision in lane_decisions if decision not in ranked_options and decision not in stock_review
        ],
        "pass_count": len(pass_rows),
        "pass_observations": [_stock_summary(row) for row in pass_rows[:12]],
        "direct_ipo_options_rule": "Direct IPO symbol is stock-review only until listed options exist and broker-visible options truth is supplied.",
        "stock_lane_allowed": True,
        "options_lane_allowed_only_after": [
            "VALID_CANDIDATE stock setup",
            "Clear direction",
            "OPTIONS_CHAIN_ACCEPTABLE",
            "SMALL_ACCOUNT_SCALP_ACCEPTABLE",
            "Manual broker snapshot/preflight for real money",
        ],
        "next_action": next_action,
        "links": {
            "event_playbook": "/ops/event-volatility-playbook?format=html",
            "event_scan_refresh": f"/ops/event-volatility-scan?event_name={event_key}&tickers={','.join(universe)}&max_candidates={max_candidates}&account_value={_float_or_zero(account_value) or 50.0}&review_top_n={review_top_n}&max_contract_price={effective_contract_cap}&format=html",
            "manual_preflight": "/review/manual-preflight?format=html",
            "paper_summary": "/paper/options/summary?format=html",
            "session_risk": f"/risk/session?account_value={_float_or_zero(account_value) or 50.0}&format=html",
        },
        "safety": {
            "review_only": True,
            "place_orders": False,
            "market_orders_allowed": False,
            "manual_approval_required": True,
            "paper_research_uncapped": True,
            "real_cash_daily_closed_loss_lockout_count": service_container.settings.max_daily_real_cash_closed_losses,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        },
        "raw_reviews": list(reviews.values()),
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "order_allowed": False,
        "notes": [
            "This event scan can classify stock/options lanes, but it cannot place, simulate, modify, or cancel broker orders.",
            "A stock review lane is allowed when options data is the weak link.",
            "No options candidate is ranked unless small-account review is acceptable.",
        ],
    }
    return service_container.events.log("event_volatility_scan", payload)


def _run_broad_opportunity_scan(
    service_container,
    tickers: list[str] | None,
    max_candidates: int,
    account_value: float,
    review_top_n: int,
    max_contract_price: float | None,
    include_event_context: bool,
) -> dict:
    max_candidates = max(1, min(int(max_candidates or 25), 50))
    review_top_n = max(1, min(int(review_top_n or 10), 25))
    universe = _broad_opportunity_universe(service_container, tickers, include_event_context)
    event_universe = set(_event_volatility_universe(service_container, None))
    microcap_universe = set(getattr(service_container.settings, "microcap_research_watchlist", ()))
    crypto_symbols = list(getattr(service_container.settings, "crypto_research_symbols", ()))
    effective_contract_cap = max_contract_price
    if effective_contract_cap is None:
        effective_contract_cap = service_container.settings.scalp_max_contract_price

    scan = service_container.scanner.run_market_scan("scalp_review", universe, max_candidates)
    stock_candidates = [
        row
        for row in (scan.get("top_candidates") or [])
        if row.get("status") == "CANDIDATE"
        and (row.get("quality_gates") or {}).get("stock_setup_quality") == "VALID_CANDIDATE"
        and str(row.get("direction") or "").lower() in {"long", "short"}
    ]
    reviews: dict[str, dict[str, Any]] = {}
    reviewable = [
        row
        for row in stock_candidates
        if str(row.get("ticker") or "").upper() not in microcap_universe
    ]
    for candidate in reviewable[:review_top_n]:
        ticker = str(candidate.get("ticker") or "").upper()
        direction = str(candidate.get("direction") or "").lower()
        option_direction = "call" if direction == "long" else "put"
        reviews[ticker] = _review_candidate_for_options(
            service_container,
            ticker,
            option_direction,
            "scalp_review",
            effective_contract_cap,
        )

    lane_decisions = [
        _broad_lane_decision(row, reviews.get(str(row.get("ticker") or "").upper()), event_universe, microcap_universe)
        for row in stock_candidates
    ]
    ranked_options = [
        decision
        for decision in lane_decisions
        if decision.get("lane") == "BROAD_OPTIONS_REVIEW_READY"
    ]
    ranked_options.sort(
        key=lambda item: (
            _float_or_zero(item.get("priority_score")),
            _float_or_zero(item.get("friction_adjusted_score")),
            -_float_or_zero(item.get("max_loss_dollars")),
        ),
        reverse=True,
    )
    stock_fallbacks = [
        decision
        for decision in lane_decisions
        if decision.get("lane") in {"STOCK_REVIEW_FALLBACK", "EVENT_STOCK_REVIEW", "INDEX_STOCK_REVIEW"}
    ]
    microcap_research = [
        decision
        for decision in lane_decisions
        if decision.get("lane") == "MICROCAP_PAPER_RESEARCH"
    ]
    non_event_candidates = [decision for decision in lane_decisions if not decision.get("event_related")]
    event_candidates = [decision for decision in lane_decisions if decision.get("event_related")]
    status = "BROAD_OPTIONS_READY" if ranked_options else "BROAD_STOCK_REVIEW_ONLY" if stock_fallbacks or microcap_research else "BROAD_NO_TRADE_PLAN"
    next_action = (
        "Review ranked broad-market options, then require manual broker snapshot/preflight for any real money."
        if ranked_options
        else "Keep observing broad stock lanes; do not force options when the contract gate is weak or unavailable."
        if stock_fallbacks or microcap_research
        else "No broad-market candidate cleared the stock setup gate. Keep scanning and harvesting."
    )
    payload = {
        "status": status,
        "build_version": BUILD_VERSION,
        "mode": "broad_opportunity_scan",
        "generated_at": utc_now(),
        "universe": universe,
        "universe_count": len(universe),
        "account_value_reference": _float_or_zero(account_value) or 50.0,
        "max_candidates": max_candidates,
        "review_top_n": review_top_n,
        "max_contract_price_used": effective_contract_cap,
        "include_event_context": bool(include_event_context),
        "scan_summary": _scan_summary(scan),
        "stock_candidate_count": len(stock_candidates),
        "options_review_count": len(reviews),
        "event_candidate_count": len(event_candidates),
        "non_event_candidate_count": len(non_event_candidates),
        "ranked_options_candidates": ranked_options,
        "stock_review_candidates": stock_fallbacks,
        "microcap_paper_research": microcap_research,
        "watch_only_or_rejected": [
            decision
            for decision in lane_decisions
            if decision not in ranked_options and decision not in stock_fallbacks and decision not in microcap_research
        ],
        "crypto_research_lane": {
            "status": "SEPARATE_PAPER_RESEARCH",
            "symbols": crypto_symbols,
            "reason": "Crypto trades 24/7 and has different spreads, volatility, catalysts, and risk mechanics. Keep it out of equity/options scoring.",
            "links": {
                "rules": "/crypto/rules",
                "backtest": "/crypto/backtest",
                "global_research": "/research/global-scan?market=crypto",
            },
        },
        "anti_tunnel_vision": {
            "event_related_candidates": [item.get("ticker") for item in event_candidates],
            "non_event_candidates": [item.get("ticker") for item in non_event_candidates],
            "rule": "Do not prefer event-adjacent names over cleaner non-event setups.",
        },
        "real_cash_test_guard": {
            "starting_cash_reference": _float_or_zero(account_value) or 50.0,
            "daily_closed_loss_lockout_count": service_container.settings.max_daily_real_cash_closed_losses,
            "market_close_stop": True,
            "microcap_real_cash_default": "DISABLED_UNTIL_PAPER_PROVEN",
            "crypto_real_cash_default": "SEPARATE_PAPER_LANE_UNTIL_RULES_PROVEN",
            "no_market_orders": True,
            "manual_approval_required": True,
        },
        "next_action": next_action,
        "links": {
            "event_radar": "/ops/event-radar?format=html",
            "broad_scan_refresh": f"/ops/broad-opportunity-scan?tickers={','.join(universe)}&max_candidates={max_candidates}&account_value={_float_or_zero(account_value) or 50.0}&review_top_n={review_top_n}&max_contract_price={effective_contract_cap}&include_event_context=true&format=html",
            "live_review_cycle": f"/ops/live-review-cycle?tickers={','.join(universe)}&account_value={_float_or_zero(account_value) or 50.0}&max_candidates={max_candidates}&review_top_n={review_top_n}&max_contract_price={effective_contract_cap}&format=html",
            "manual_preflight": "/review/manual-preflight?format=html",
            "paper_summary": "/paper/options/summary?format=html",
        },
        "safety": {
            "review_only": True,
            "place_orders": False,
            "market_orders_allowed": False,
            "manual_approval_required": True,
            "paper_research_uncapped": True,
            "real_cash_daily_closed_loss_lockout_count": service_container.settings.max_daily_real_cash_closed_losses,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        },
        "raw_reviews": list(reviews.values()),
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "order_allowed": False,
        "notes": [
            "Broad scan is the default opportunity engine. Event radar adds context but cannot narrow the machine by itself.",
            "Microcap and crypto lanes are separated to prevent contaminated learning.",
            "This MCP cannot place, simulate, modify, or cancel broker orders.",
        ],
    }
    return service_container.events.log("broad_opportunity_scan", payload)


def _broad_lane_decision(
    stock_row: dict[str, Any],
    review: dict[str, Any] | None,
    event_universe: set[str],
    microcap_universe: set[str],
) -> dict[str, Any]:
    ticker = str(stock_row.get("ticker") or "").upper()
    direction = str(stock_row.get("direction") or "").lower()
    signals = stock_row.get("key_signals") or {}
    vwap_state = "above" if signals.get("above_vwap") else "below" if signals.get("below_vwap") else "unknown"
    base = {
        "ticker": ticker,
        "stock_direction": direction,
        "stock_score": stock_row.get("score"),
        "relative_volume": signals.get("relative_volume"),
        "vwap_state": vwap_state,
        "stock_setup_quality": (stock_row.get("quality_gates") or {}).get("stock_setup_quality"),
        "stock_status": stock_row.get("status"),
        "event_related": ticker in event_universe,
        "why_not_ranked": [],
        "review_only": True,
        "order_allowed": False,
    }
    if ticker in microcap_universe:
        return {
            **base,
            "lane": "MICROCAP_PAPER_RESEARCH",
            "rankable_as_options": False,
            "real_cash_enabled": False,
            "why_not_ranked": ["Microcap symbols are paper/research only until slippage, spread, halt risk, and repeatability are proven."],
        }
    if not review:
        lane = "EVENT_STOCK_REVIEW" if ticker in event_universe else "INDEX_STOCK_REVIEW" if ticker in {"SPY", "QQQ", "IWM"} else "STOCK_REVIEW_FALLBACK"
        return {
            **base,
            "lane": lane,
            "rankable_as_options": False,
            "why_not_ranked": ["Stock setup passed, but no rankable options review is available in this pass."],
        }
    small = review.get("small_account_review") or {}
    selected = small.get("selected_contract") or {}
    option_ready = review.get("status") == "REVIEW_ONLY_OPTIONS_READY" and small.get("status") == "SMALL_ACCOUNT_SCALP_ACCEPTABLE"
    if option_ready:
        return {
            **base,
            "lane": "BROAD_OPTIONS_REVIEW_READY",
            "rankable_as_options": True,
            "option_direction": "call" if direction == "long" else "put",
            "priority_score": small.get("priority_score"),
            "friction_adjusted_score": small.get("friction_adjusted_score"),
            "friction_band": small.get("friction_band"),
            "selected_contract": selected.get("contract_symbol"),
            "ask": selected.get("ask"),
            "max_loss_dollars": selected.get("max_loss_dollars"),
            "spread_pct": selected.get("spread_pct"),
            "dte": selected.get("days_to_expiration"),
            "warnings": review.get("warnings") or small.get("warnings") or [],
        }
    return {
        **base,
        "lane": "STOCK_REVIEW_FALLBACK",
        "rankable_as_options": False,
        "option_status": review.get("status"),
        "small_account_status": small.get("status"),
        "selected_contract": selected.get("contract_symbol") if selected else None,
        "why_not_ranked": [
            "Stock setup passed, but options candidate did not clear both OPTIONS_CHAIN_ACCEPTABLE and SMALL_ACCOUNT_SCALP_ACCEPTABLE.",
            review.get("reason") or "Options review did not return a rankable small-account contract.",
        ],
        "warnings": review.get("warnings") or small.get("warnings") or [],
    }


def _get_data_truth_cockpit(service_container, tickers: list[str] | None, max_tickers: int) -> dict:
    max_tickers = max(1, min(int(max_tickers or 12), 25))
    universe = _broad_opportunity_universe(service_container, tickers, include_event_context=True)[:max_tickers]
    truth = service_container.market_truth.truth_source_status()
    health = service_container.market_truth.check_market_data_health(universe, max_tickers)
    options_status = service_container.options.options_data_status()
    healthy_rows = [row for row in (health.get("rows") or []) if row.get("status") == "HEALTHY"]
    degraded_rows = [row for row in (health.get("rows") or []) if row.get("status") != "HEALTHY"]
    options_truth_ready = options_status.get("real_money_options_truth_status") == "REAL_MONEY_OPTIONS_TRUTH_READY"
    if health.get("status") == "MARKET_DATA_HEALTHY" and options_truth_ready:
        status = "DATA_TRUTH_READY"
        next_action = "Inputs are clean enough for review-only scans; still require manual broker preflight for real money."
    elif health.get("status") == "MARKET_DATA_HEALTHY":
        status = "DATA_TRUTH_EQUITY_READY_OPTIONS_MANUAL"
        next_action = "Equity data is usable. Real-money options still require broker-visible snapshot/manual preflight."
    elif healthy_rows:
        status = "DATA_TRUTH_PARTIAL"
        next_action = "Use only healthy symbols for review; do not trade symbols with degraded source rows."
    else:
        status = "DATA_TRUTH_BLOCKED"
        next_action = "Do not run real-cash review. Fix or wait for fresh quotes/candles."
    payload = {
        "status": status,
        "build_version": BUILD_VERSION,
        "generated_at": utc_now(),
        "checked_universe": universe,
        "market_data_health": {
            "status": health.get("status"),
            "provider": health.get("provider"),
            "configured_provider": health.get("configured_provider"),
            "healthy_count": len(healthy_rows),
            "degraded_count": len(degraded_rows),
            "rows": health.get("rows") or [],
        },
        "options_truth": options_status,
        "truth_source_status": {
            "market_data": truth.get("market_data"),
            "cash_readiness": truth.get("cash_readiness"),
            "blocked_for_cash_without": truth.get("blocked_for_cash_without"),
        },
        "source_priority": [
            "Provider quote/candle data for broad scans.",
            "Broker-visible manual snapshot for real-money option truth.",
            "Robinhood watchlists only as organization/context unless a callable quote/chain tool proves live data.",
            "Paper ledger and journal checkpoints for learning continuity.",
        ],
        "robinhood_level_2_decision": {
            "recommendation": "WAIT_FOR_TOOL_PROOF",
            "reason": "Do not subscribe solely for this system until the connected tool surface exposes useful live quote/order-book/options-chain fields. UI-only Level II does not automatically solve MCP data truth.",
            "subscribe_when": [
                "Robinhood tool list exposes callable live equity/order-book quote fields useful to the MCP.",
                "Or it exposes live options bid/ask/volume/open-interest/chain data we can validate.",
                "Or manual broker snapshots become the bottleneck and Level II visibly improves your human preflight quality.",
            ],
        },
        "cash_test_readiness": {
            "paper_research_uncapped": True,
            "real_cash_daily_closed_loss_lockout_count": service_container.settings.max_daily_real_cash_closed_losses,
            "market_close_stop": True,
            "real_cash_allowed_only_after": [
                "DATA_TRUTH_READY or DATA_TRUTH_EQUITY_READY_OPTIONS_MANUAL",
                "Candidate clears the relevant lane gates.",
                "Manual broker snapshot/preflight confirms current truth.",
                "No market order.",
                "Manual approval outside MCP.",
            ],
        },
        "next_action": next_action,
        "links": {
            "data_truth_cockpit": "/ops/data-truth-cockpit?format=html",
            "market_data_health": f"/market/data-health?tickers={','.join(universe)}&max_tickers={max_tickers}",
            "truth_source_status": "/truth/source-status",
            "options_data_status": "/options/data-status",
            "broad_opportunity_scan": "/ops/broad-opportunity-scan?format=html",
            "manual_trade_desk": "/trade/manual-desk?format=html",
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
    }
    return service_container.events.log("data_truth_cockpit", payload)


def _get_system_communication_audit(service_container) -> dict:
    recent_events = service_container.events.recent(None, 250)
    event_counts = Counter(event.get("event_type") for event in recent_events)
    payload = {
        "status": "SYSTEM_COMMUNICATION_AUDIT_READY",
        "build_version": BUILD_VERSION,
        "generated_at": utc_now(),
        "recent_event_count": len(recent_events),
        "recent_event_type_counts": dict(event_counts),
        "communication_map": [
            {"system": "scanner", "writes": ["scan rows", "evidence_packet", "evidence_scorecard", "quote/candle lineage"], "read_by": ["review harvest", "observer", "broad opportunity scan", "learning"], "clutter_control": "Compact row summaries plus evidence flags; raw scans are not treated as orders."},
            {"system": "options review", "writes": ["candidate_options_review", "small_account_review", "friction score", "setup memory"], "read_by": ["live review cycle", "manual trade desk", "learning"], "clutter_control": "Only SMALL_ACCOUNT_SCALP_ACCEPTABLE can be ranked as an options review candidate."},
            {"system": "paper/manual journal", "writes": ["paper option entries/closes", "manual broker actions", "pending recheck cards"], "read_by": ["session risk", "learning", "command center", "alerts"], "clutter_control": "Paper and real-cash counters are separated; real-cash lockout uses user-reported real-cash closes only."},
            {"system": "event radar", "writes": ["event context", "event/non-event candidate separation"], "read_by": ["broad opportunity scan", "operator"], "clutter_control": "Event context cannot replace broad scan and cannot rank messy event names above cleaner setups."},
            {"system": "crypto/global research", "writes": ["paper-only crypto backtests", "global research observations"], "read_by": ["learning/research only"], "clutter_control": "Crypto is kept out of equity/options scoring unless explicitly tested in its own lane."},
        ],
        "clutter_limits": [
            "Each route returns a status and next_action, not just raw data.",
            "Event, broad equity/options, microcap, and crypto lanes are labeled separately.",
            "Learning proposals are do_not_auto_apply until backtested and manually accepted.",
            "Journal checkpoints are used to preserve useful evidence without relying on Render local disk.",
            "Broker/watchlist data is treated as context unless it supplies explicit live truth fields.",
        ],
        "known_weak_links": [
            "Render local SQLite is not durable without checkpoint export/restore.",
            "Options truth is still manual/broker-snapshot unless a realtime options provider is configured.",
            "Robinhood watchlist visibility does not equal live options-chain validation.",
            "Too many scan rows can create operator noise; use broad scan ranking plus alerts to focus attention.",
        ],
        "next_action": "Keep the day monitor, data truth cockpit, broad scan, paper summary, and journal checkpoint pages open. Export checkpoint after meaningful reviews.",
        "links": {
            "command_center": "/ops/command-center?format=html",
            "data_truth_cockpit": "/ops/data-truth-cockpit?format=html",
            "broad_scan": "/ops/broad-opportunity-scan?format=html",
            "learning_dashboard": "/learning/dashboard?format=html",
            "journal_checkpoint": "/journal/checkpoint?limit=500&format=html",
        },
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
    }
    return service_container.events.log("system_communication_audit", payload)


def _get_strategy_module_registry(service_container) -> dict:
    modules = [
        ("clean_liquid_options_scalp", "REVIEW_ONLY", "Core small-account options scalp. Needs broker-visible options truth for cash."),
        ("relative_strength_calls", "REVIEW_ONLY", "Long setups leading SPY/QQQ with VWAP and volume confirmation."),
        ("relative_weakness_puts", "REVIEW_ONLY", "Short setups lagging SPY/QQQ with below-VWAP pressure."),
        ("vwap_reclaim", "REVIEW_ONLY", "Reclaim plus confirmation; avoid first-candle fakeouts."),
        ("vwap_rejection", "REVIEW_ONLY", "Failed reclaim / rejection with downside continuation."),
        ("opening_range_breakout", "REVIEW_ONLY", "Observe first minutes; enable only after false-breakout filters mature."),
        ("failed_breakout_reversal", "REVIEW_ONLY", "Useful defensive and reversal detector; not cash-autonomous yet."),
        ("power_hour_continuation", "REVIEW_ONLY", "Late-day momentum scanner; overnight rules remain stricter."),
        ("overnight_swing", "DISABLED_FOR_CASH", "Only exceptional setups; too much gap risk for early $100 autonomy."),
        ("microcap_ignition", "PAPER_ONLY", "Separate high-risk watchboard; real cash disabled until slippage/halt risk is proven."),
        ("gap_fill", "REVIEW_ONLY", "Needs time-of-day and regime performance before cash use."),
        ("news_catalyst_momentum", "REVIEW_ONLY", "Catalyst context is useful but not sufficient without price/liquidity truth."),
        ("index_trend_following", "REVIEW_ONLY", "SPY/QQQ/IWM regime confirmation and possible safer stock lane."),
        ("sector_rotation", "NEEDS_DATA", "High-value upgrade; sector-relative strength remains a known gap."),
        ("high_relative_volume_momentum", "REVIEW_ONLY", "Priority signal, not a hard approval; backtests rejected RVOL as a standalone gate."),
    ]
    recent_classifications = service_container.events.recent("learning_outcome_classification", 500)
    classification_counts = Counter(str((event.get("payload") or {}).get("classification") or "unknown") for event in recent_classifications)
    payload = {
        "status": "STRATEGY_MODULE_REGISTRY_READY",
        "build_version": BUILD_VERSION,
        "schema_version": "strategy_module_registry_v1",
        "generated_at": utc_now(),
        "module_count": len(modules),
        "modules": [
            {
                "module": name,
                "status": status,
                "cash_autonomous_enabled": False,
                "paper_enabled": status != "DISABLED_FOR_CASH",
                "reason": reason,
                "required_before_cash": [
                    "fresh market data",
                    "fresh options/broker snapshot if options",
                    "positive expectancy from enough samples",
                    "known false-positive filters",
                    "active risk lockout and kill switch",
                ],
            }
            for name, status, reason in modules
        ],
        "live_performance_memory": {
            "status": "INSUFFICIENT_LIVE_SAMPLE_FOR_AUTONOMOUS_CASH",
            "classification_counts": dict(classification_counts),
            "sample_size": len(recent_classifications),
            "minimum_before_cash_enablement": 30,
            "notes": "Use module memory to disable bad strategies and prioritize paper, not to weaken core safety rules.",
        },
        "autonomous_adjustment_permissions": {
            "may_adjust": [
                "candidate scoring",
                "watchlist priority",
                "strategy confidence",
                "strategy enable/disable status",
                "entry/exit timing preferences",
                "position size downward after drawdown",
                "liquidity/spread rules only stricter",
            ],
            "may_not_adjust": [
                "max daily loss upward",
                "kill switch removal",
                "market order restriction",
                "stale-data shutdown",
                "broker error shutdown",
                "minimum liquidity downward",
                "maximum spread tolerance upward",
                "revenge-trade restrictions",
            ],
        },
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "order_allowed": False,
    }
    return service_container.events.log("strategy_module_registry", payload)


def _get_shared_intelligence_layer(service_container, tickers: list[str] | None, limit_events: int) -> dict:
    limit_events = max(10, min(int(limit_events or 100), 500))
    universe_filter = {str(ticker).upper() for ticker in (tickers or []) if str(ticker).strip()}
    source_events = []
    for event_type in (
        "market_open_observer",
        "paper_exploration_run",
        "paper_exploration_followup",
        "live_review_cycle",
        "broad_opportunity_scan",
        "event_volatility_scan",
        "learning_outcome_classification",
    ):
        source_events.extend(service_container.events.recent(event_type, limit_events))
    source_events = sorted(source_events, key=lambda event: int(event.get("id") or 0), reverse=True)[:limit_events]
    signals: list[dict[str, Any]] = []
    for event in source_events:
        signals.extend(_intelligence_signals_from_event(event, event.get("payload") or {}, universe_filter))
    scored = [_score_intelligence_signal(signal) for signal in signals]
    actionable = [item for item in scored if item["final_use"] == "ACTIONABLE"]
    supporting = [item for item in scored if item["final_use"] == "SUPPORTING_CONFIRMATION"]
    suppressed = [item for item in scored if item["final_use"] in {"SUPPRESSED_NOISE", "STALE_OR_LOW_CONFIDENCE", "BACKGROUND_ONLY"}]
    payload = {
        "status": "SHARED_INTELLIGENCE_READY",
        "build_version": BUILD_VERSION,
        "schema_version": "shared_intelligence_v1",
        "generated_at": utc_now(),
        "source_event_count": len(source_events),
        "signal_count": len(scored),
        "actionable_count": len(actionable),
        "supporting_count": len(supporting),
        "suppressed_count": len(suppressed),
        "conflict_count": sum(1 for item in scored if item.get("signal_class") == "contradictory_information"),
        "escalation_count": sum(1 for item in scored if item.get("escalate")),
        "hierarchy": [
            "risk_controls",
            "broker_order_safety",
            "fresh_market_data",
            "liquidity_and_spread",
            "market_regime",
            "price_action",
            "volume_confirmation",
            "vwap_key_levels",
            "options_chain_quality",
            "catalyst_event_risk",
            "strategy_specific_signals",
            "background_context",
        ],
        "actionable_signals": actionable[:20],
        "supporting_confirmations": supporting[:20],
        "suppressed_or_background": suppressed[:20],
        "noise_filter_rules": [
            "Unknown information never becomes confidence.",
            "More signals are not automatically better.",
            "Weak clues are logged but do not trigger trades.",
            "Contradictions reduce confidence; unresolved trade-critical contradictions force PASS.",
            "Risk controls always override opportunity signals.",
        ],
        "cash_decision_rule": "Only ACTIONABLE plus high-quality SUPPORTING_CONFIRMATION can influence autonomous cash; this MCP still cannot execute broker orders.",
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "order_allowed": False,
    }
    return service_container.events.log("shared_intelligence_layer", payload)


def _get_autonomous_launch_decision(service_container, account_value: float, intended_cash: float, tickers: list[str] | None) -> dict:
    account_value = _float_or_zero(account_value) or 100.0
    intended_cash = _float_or_zero(intended_cash) or account_value
    universe = _resolve_universe(service_container, tickers)
    safety = get_safety_config()
    truth = _get_data_truth_cockpit(service_container, universe, 12)
    options_status = service_container.options.options_data_status()
    session_risk = _get_session_risk_guard(service_container, account_value, None, 2)
    paper = _summarize_paper_exploration(service_container, 100)
    ledger = _summarize_manual_option_paper_trades(service_container, 100)
    registry = _get_strategy_module_registry(service_container)
    intelligence = _get_shared_intelligence_layer(service_container, universe, 100)
    blockers: list[str] = []
    warnings: list[str] = []
    if safety.get("can_place_order_from_this_mcp") is not False:
        blockers.append("Unexpected broker execution capability state.")
    blockers.append("This MCP has no broker execution capability; autonomous real-money execution cannot be enabled here.")
    if options_status.get("real_money_options_truth_status") != "REAL_MONEY_OPTIONS_TRUTH_READY":
        blockers.append("Real-money options truth is not automated; broker snapshot/manual or provider truth is required.")
    if (truth.get("market_data_health") or {}).get("status") not in {"MARKET_DATA_HEALTHY", "MARKET_DATA_PARTIAL"}:
        blockers.append("Market data health is not clean enough for cash launch.")
    if ledger.get("closed_count", 0) < 10 and paper.get("opened_entry_count", 0) < 20:
        warnings.append("Paper/live sample size is still thin; increase paper exploration and follow-up before trusting cash automation.")
    if session_risk.get("status") == "SESSION_RISK_BLOCKED":
        blockers.append("Session risk guard is blocked.")
    payload = {
        "status": "AUTONOMOUS_FIREWALL_READY",
        "build_version": BUILD_VERSION,
        "schema_version": "autonomous_launch_decision_v1",
        "generated_at": utc_now(),
        "account_value_reference": account_value,
        "intended_cash_reference": intended_cash,
        "stretch_goal": {
            "target": "Turn $100 into $1,000,000 in 5 trading days",
            "classification": "ASPIRATIONAL_MOONSHOT_NOT_A_RISK_RULE",
            "reality_rule": "The system must never chase this target by violating risk, liquidity, probability, or data-quality requirements.",
        },
        "capability_decision": {
            "autonomous_scanning_enabled": True,
            "autonomous_paper_exploration_enabled": True,
            "autonomous_real_money_execution_enabled": False,
            "cash_gate_changed": False,
        },
        "blockers": blockers,
        "warnings": warnings,
        "data_readiness": {
            "market_data_health": (truth.get("market_data_health") or {}).get("status"),
            "options_truth": options_status.get("real_money_options_truth_status"),
            "options_next_step": options_status.get("next_step"),
            "missing_or_manual": [
                "broker execution validator outside this MCP",
                "broker buying-power validator outside this MCP",
                "broker open-order/open-position validator outside this MCP",
                "broker-visible option bid/ask/volume/OI truth or paid provider",
            ],
        },
        "risk_readiness": {
            "session_risk_status": session_risk.get("status"),
            "warning_drawdown_pct": 0.10,
            "soft_lockout_pct": 0.20,
            "hard_shutdown_pct": 0.30,
            "no_market_orders": True,
            "three_loss_cash_lockout": True,
        },
        "learning_readiness": {
            "paper_exploration_runs": paper.get("run_count"),
            "paper_exploration_trials": paper.get("trial_count"),
            "paper_exploration_opened": paper.get("opened_entry_count"),
            "manual_paper_closed": ledger.get("closed_count"),
            "manual_paper_win_rate": ledger.get("win_rate"),
            "next_learning_action": "Run paper exploration, wait for candles, run follow-up, then classify what helped/hurt.",
        },
        "system_intelligence": {
            "registry_status": registry.get("status"),
            "shared_intelligence_status": intelligence.get("status"),
            "actionable_signals": intelligence.get("actionable_count"),
            "suppressed_signals": intelligence.get("suppressed_count"),
            "conflicts": intelligence.get("conflict_count"),
        },
        "minimum_before_cash_autonomy": [
            "Separate broker tool confirms account, buying power, positions, and open orders.",
            "Order preview/check exists and rejects failing tickets before submission.",
            "Automated fresh options truth exists or manual snapshot keeps execution human-reviewed.",
            "Paper exploration and follow-up produce enough labeled winners/losers.",
            "Strategy module has positive expectancy and known failure filters.",
            "Kill switch and daily drawdown lockout are tested live.",
        ],
        "live_trading_rules_for_tomorrow": {
            "premarket": ["validate data", "construct broad watchlist", "check catalysts", "confirm risk lockouts"],
            "open": ["no blind trades", "observe first minutes unless exceptional", "reject wide spreads"],
            "first_30_minutes": ["track opening range", "track VWAP", "avoid first-candle chase"],
            "midday": ["reduce aggression", "avoid chop", "prefer only clean continuation or reclaim/rejection"],
            "power_hour": ["rescan", "consider overnight only after strict swing gate", "do not hold weak scalps"],
            "shutdown": ["3 real-cash closed losses", "30% drawdown", "stale data", "broker/API uncertainty", "market close for scalps"],
        },
        "final_launch_decision": "DELAY_LAUNCH" if blockers else "REVIEW_ONLY",
        "operator_read": "Autonomous scanning and paper learning are enabled. Autonomous real-money execution is delayed/review-only until broker and options truth gates are actually present.",
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "order_allowed": False,
        "broker_action": False,
    }
    return service_container.events.log("autonomous_launch_decision", payload)


def _proof_item(category: str, name: str, status: str, evidence: str, required_for: list[str]) -> dict[str, Any]:
    return {
        "category": category,
        "name": name,
        "status": status,
        "evidence": evidence,
        "required_for": required_for,
    }


def _get_real_cash_proof_gate(
    service_container,
    account_value: float,
    intended_cash: float,
    tickers: list[str] | None,
    broker_account_confirmed: bool,
    buying_power_confirmed: bool,
    open_orders_checked: bool,
    open_positions_checked: bool,
    no_duplicate_order_confirmed: bool,
    order_preview_confirmed: bool,
    options_snapshot_validated: bool,
    separate_broker_executor_proven: bool,
) -> dict:
    account_value = _float_or_zero(account_value) or 100.0
    intended_cash = _float_or_zero(intended_cash) or account_value
    universe = _resolve_universe(service_container, tickers)
    safety = get_safety_config()
    truth = _get_data_truth_cockpit(service_container, universe, 12)
    options_status = service_container.options.options_data_status()
    session_risk = _get_session_risk_guard(service_container, account_value, None, 2)
    paper = _summarize_paper_exploration(service_container, 100)
    manual_paper = _summarize_manual_option_paper_trades(service_container, 100)
    intelligence = _get_shared_intelligence_layer(service_container, universe, 100)
    options_truth_ready = options_status.get("real_money_options_truth_status") == "REAL_MONEY_OPTIONS_TRUTH_READY" or bool(options_snapshot_validated)
    market_health = (truth.get("market_data_health") or {}).get("status")
    market_data_ready = market_health in {"MARKET_DATA_HEALTHY", "MARKET_DATA_PARTIAL"}
    session_risk_clear = session_risk.get("status") != "SESSION_RISK_BLOCKED"
    paper_sample_size = int(paper.get("opened_entry_count") or 0) + int(manual_paper.get("closed_count") or 0)
    proof_items = [
        _proof_item("build", "Expected build is running", "PROVEN", BUILD_VERSION, ["scan", "manual_cash_review", "autonomous_execution"]),
        _proof_item("safety", "MCP cannot place or cancel broker orders", "PROVEN", "can_place_order_from_this_mcp=false; can_cancel_order_from_this_mcp=false", ["scan", "manual_cash_review"]),
        _proof_item("safety", "No market orders", "PROVEN" if not safety.get("market_orders_allowed") else "BLOCKED", f"market_orders_allowed={safety.get('market_orders_allowed')}", ["manual_cash_review", "autonomous_execution"]),
        _proof_item("safety", "Manual approval phrase required", "PROVEN" if safety.get("manual_approval_required") else "BLOCKED", str(safety.get("approval_phrase")), ["manual_cash_review"]),
        _proof_item("data", "Fresh/usable market data", "PROVEN" if market_data_ready else "MISSING", str(market_health), ["scan", "manual_cash_review", "autonomous_execution"]),
        _proof_item("options", "Real-money options truth", "PROVEN" if options_truth_ready else "MISSING", options_status.get("real_money_options_truth_status") or "unknown", ["manual_cash_review", "autonomous_execution"]),
        _proof_item("broker", "Broker account selected and confirmed", "PROVEN" if broker_account_confirmed else "MISSING", "operator/broker confirmation required", ["manual_cash_review", "autonomous_execution"]),
        _proof_item("broker", "Buying power confirmed", "PROVEN" if buying_power_confirmed else "MISSING", "operator/broker confirmation required", ["manual_cash_review", "autonomous_execution"]),
        _proof_item("broker", "Open orders checked", "PROVEN" if open_orders_checked else "MISSING", "must prevent stale or duplicate pending orders", ["manual_cash_review", "autonomous_execution"]),
        _proof_item("broker", "Open positions checked", "PROVEN" if open_positions_checked else "MISSING", "must prevent accidental overexposure", ["manual_cash_review", "autonomous_execution"]),
        _proof_item("broker", "Duplicate order prevented", "PROVEN" if no_duplicate_order_confirmed else "MISSING", "must prove no duplicate ticket is active", ["manual_cash_review", "autonomous_execution"]),
        _proof_item("broker", "Limit-order preview confirmed", "PROVEN" if order_preview_confirmed else "MISSING", "exact symbol, contract, quantity, limit, max loss", ["manual_cash_review", "autonomous_execution"]),
        _proof_item("risk", "Session risk is not blocked", "PROVEN" if session_risk_clear else "BLOCKED", str(session_risk.get("status")), ["manual_cash_review", "autonomous_execution"]),
        _proof_item("learning", "Minimum paper/live learning sample", "PROVEN" if paper_sample_size >= 20 else "WARNING", f"sample_size={paper_sample_size}; target>=20 before trust", ["autonomous_execution"]),
        _proof_item("broker_execution", "Separate broker executor proven", "PROVEN" if separate_broker_executor_proven else "BLOCKED", "this MCP has no broker execution path", ["autonomous_execution"]),
    ]
    manual_blockers = [
        item for item in proof_items
        if "manual_cash_review" in item["required_for"] and item["status"] in {"MISSING", "BLOCKED"}
    ]
    autonomous_blockers = [
        item for item in proof_items
        if "autonomous_execution" in item["required_for"] and item["status"] in {"MISSING", "BLOCKED"}
    ]
    warnings = [item for item in proof_items if item["status"] == "WARNING"]
    payload = {
        "status": "REAL_CASH_PROOF_GATE_READY",
        "build_version": BUILD_VERSION,
        "schema_version": "real_cash_proof_gate_v1",
        "generated_at": utc_now(),
        "account_value_reference": account_value,
        "intended_cash_reference": intended_cash,
        "universe": universe,
        "proof_summary": {
            "proof_item_count": len(proof_items),
            "proven_count": sum(1 for item in proof_items if item["status"] == "PROVEN"),
            "missing_count": sum(1 for item in proof_items if item["status"] == "MISSING"),
            "blocked_count": sum(1 for item in proof_items if item["status"] == "BLOCKED"),
            "warning_count": len(warnings),
        },
        "decisions": {
            "autonomous_scanning": "PROVEN_READY" if market_data_ready else "BLOCKED_BY_DATA",
            "aggressive_paper_learning": "PROVEN_READY",
            "manual_real_cash_review": "REAL_CASH_PROOF_READY" if not manual_blockers else "REAL_CASH_BLOCKED",
            "fully_autonomous_real_cash_execution": "AUTONOMOUS_EXECUTION_PROOF_READY" if not autonomous_blockers and not warnings else "AUTONOMOUS_EXECUTION_BLOCKED",
        },
        "proof_items": proof_items,
        "manual_cash_blockers": manual_blockers,
        "autonomous_execution_blockers": autonomous_blockers,
        "warnings": warnings,
        "source_snapshots": {
            "safety": safety,
            "market_data_health": truth.get("market_data_health"),
            "options_data_status": options_status,
            "session_risk_guard": session_risk,
            "paper_exploration_summary": {
                "run_count": paper.get("run_count"),
                "opened_entry_count": paper.get("opened_entry_count"),
                "trial_count": paper.get("trial_count"),
            },
            "manual_paper_summary": {
                "closed_count": manual_paper.get("closed_count"),
                "win_rate": manual_paper.get("win_rate"),
            },
            "shared_intelligence": {
                "status": intelligence.get("status"),
                "signal_count": intelligence.get("signal_count"),
                "actionable_count": intelligence.get("actionable_count"),
                "conflict_count": intelligence.get("conflict_count"),
            },
        },
        "next_step": "Keep autonomous scanning and paper learning on. For real cash, satisfy every manual_cash_blocker with broker-visible proof before manual action. Fully autonomous cash remains blocked until a separate broker executor and order-preview loop are proven.",
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "order_allowed": False,
        "broker_action": False,
    }
    return service_container.events.log("real_cash_proof_gate", payload)


def _get_broker_proof_bridge(
    service_container,
    account_value: float,
    intended_cash: float,
    ticker: str,
    contract_symbol: str,
    account_last4: str,
    account_type: str,
    broker_account_confirmed: bool,
    buying_power_confirmed: bool,
    buying_power: float | None,
    open_orders_checked: bool,
    open_order_count: int | None,
    open_positions_checked: bool,
    open_position_count: int | None,
    duplicate_order_active: bool,
    order_preview_confirmed: bool,
    preview_order_type: str,
    preview_side: str,
    preview_quantity: int,
    preview_limit_price: float | None,
    preview_max_loss: float | None,
    options_snapshot_validated: bool,
    options_snapshot_age_seconds: float | None,
    broker_source: str,
    separate_broker_executor_proven: bool,
) -> dict:
    account_value = _float_or_zero(account_value) or 100.0
    intended_cash = _float_or_zero(intended_cash) or account_value
    ticker = str(ticker or "").upper().strip()
    contract_symbol = str(contract_symbol or "").upper().strip()
    account_last4 = str(account_last4 or "").strip()
    account_type = str(account_type or "").strip()
    broker_source = str(broker_source or "operator_supplied").strip().lower()
    order_type = str(preview_order_type or "").strip().lower()
    side = str(preview_side or "").strip().lower()
    qty = max(0, int(preview_quantity or 0))
    limit_price = _float_or_zero(preview_limit_price)
    max_loss = _float_or_zero(preview_max_loss)
    buying_power_value = _float_or_zero(buying_power)
    snapshot_age = _float_or_zero(options_snapshot_age_seconds)
    machine_verified = broker_source in {"machine_verified", "robinhood_mcp_verified", "broker_api_verified"}
    required_cash = max(max_loss, min(intended_cash, account_value))
    open_orders_count_valid = open_order_count is not None and int(open_order_count) >= 0
    open_positions_count_valid = open_position_count is not None and int(open_position_count) >= 0

    broker_items = [
        _proof_item("broker", "Broker account selected", "PROVEN" if broker_account_confirmed and account_last4 else "MISSING", account_last4 or "missing account identifier", ["manual_cash_review", "autonomous_execution"]),
        _proof_item("broker", "Broker account type recorded", "PROVEN" if account_type else "WARNING", account_type or "account type missing", ["manual_cash_review"]),
        _proof_item("broker", "Buying power numeric and sufficient", "PROVEN" if buying_power_confirmed and buying_power_value >= required_cash else "MISSING", f"buying_power={buying_power_value}; required_reference={round(required_cash, 2)}", ["manual_cash_review", "autonomous_execution"]),
        _proof_item("broker", "Open orders checked", "PROVEN" if open_orders_checked and open_orders_count_valid else "MISSING", f"open_order_count={open_order_count}", ["manual_cash_review", "autonomous_execution"]),
        _proof_item("broker", "Open positions checked", "PROVEN" if open_positions_checked and open_positions_count_valid else "MISSING", f"open_position_count={open_position_count}", ["manual_cash_review", "autonomous_execution"]),
        _proof_item("broker", "No duplicate active order", "PROVEN" if not duplicate_order_active and open_orders_checked else "BLOCKED", f"duplicate_order_active={duplicate_order_active}", ["manual_cash_review", "autonomous_execution"]),
        _proof_item("broker", "Limit-order preview confirmed", "PROVEN" if order_preview_confirmed and order_type == "limit" and qty > 0 and limit_price > 0 and max_loss > 0 else "MISSING", f"type={order_type}; qty={qty}; limit={limit_price}; max_loss={max_loss}", ["manual_cash_review", "autonomous_execution"]),
        _proof_item("options", "Fresh options snapshot validated", "PROVEN" if options_snapshot_validated and snapshot_age > 0 and snapshot_age <= 60 else "MISSING", f"validated={options_snapshot_validated}; age_seconds={snapshot_age}", ["manual_cash_review", "autonomous_execution"]),
        _proof_item("execution", "Broker proof source is machine verified", "PROVEN" if machine_verified else "WARNING", broker_source, ["autonomous_execution"]),
        _proof_item("execution", "Separate broker executor proven", "PROVEN" if separate_broker_executor_proven else "BLOCKED", "required for autonomous execution; not required for manual review", ["autonomous_execution"]),
    ]
    manual_blockers = [
        item for item in broker_items
        if "manual_cash_review" in item["required_for"] and item["status"] in {"MISSING", "BLOCKED"}
    ]
    autonomy_blockers = [
        item for item in broker_items
        if "autonomous_execution" in item["required_for"] and item["status"] in {"MISSING", "BLOCKED", "WARNING"}
    ]
    proof_gate_query = (
        f"account_value={account_value}&intended_cash={intended_cash}"
        f"&broker_account_confirmed={str(broker_account_confirmed).lower()}"
        f"&buying_power_confirmed={str(bool(buying_power_confirmed and buying_power_value >= required_cash)).lower()}"
        f"&open_orders_checked={str(bool(open_orders_checked and open_orders_count_valid)).lower()}"
        f"&open_positions_checked={str(bool(open_positions_checked and open_positions_count_valid)).lower()}"
        f"&no_duplicate_order_confirmed={str(bool(not duplicate_order_active and open_orders_checked)).lower()}"
        f"&order_preview_confirmed={str(bool(order_preview_confirmed and order_type == 'limit' and qty > 0 and limit_price > 0 and max_loss > 0)).lower()}"
        f"&options_snapshot_validated={str(bool(options_snapshot_validated and snapshot_age > 0 and snapshot_age <= 60)).lower()}"
        f"&separate_broker_executor_proven={str(bool(separate_broker_executor_proven and machine_verified)).lower()}"
    )
    payload = {
        "status": "BROKER_PROOF_AUTONOMY_READY" if not autonomy_blockers else "BROKER_PROOF_MANUAL_READY" if not manual_blockers else "BROKER_PROOF_INCOMPLETE",
        "build_version": BUILD_VERSION,
        "schema_version": "broker_proof_bridge_v1",
        "generated_at": utc_now(),
        "ticker": ticker,
        "contract_symbol": contract_symbol,
        "account_value_reference": account_value,
        "intended_cash_reference": intended_cash,
        "broker_source": broker_source,
        "machine_verified": machine_verified,
        "broker_snapshot": {
            "account_last4": account_last4,
            "account_type": account_type,
            "buying_power": buying_power_value,
            "open_order_count": open_order_count,
            "open_position_count": open_position_count,
        },
        "order_preview": {
            "type": order_type,
            "side": side,
            "quantity": qty,
            "limit_price": limit_price,
            "max_loss": max_loss,
            "duplicate_order_active": duplicate_order_active,
        },
        "proof_items": broker_items,
        "manual_cash_blockers": manual_blockers,
        "autonomous_execution_blockers": autonomy_blockers,
        "decisions": {
            "manual_real_cash_review": "BROKER_PROOF_READY" if not manual_blockers else "BROKER_PROOF_BLOCKED",
            "fully_autonomous_real_cash_execution": "BROKER_AUTONOMY_PROOF_READY" if not autonomy_blockers else "BROKER_AUTONOMY_BLOCKED",
            "can_feed_real_cash_proof_gate": not manual_blockers,
        },
        "proof_gate_link": f"/ops/real-cash-proof-gate?{proof_gate_query}",
        "proof_gate_link_html": f"/ops/real-cash-proof-gate?{proof_gate_query}&format=html",
        "next_step": "If manual proof is ready, open the proof gate link. If autonomy remains blocked, do not build execution until broker source is machine verified and a separate executor/order-preview loop is proven.",
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "order_allowed": False,
        "broker_action": False,
    }
    return service_container.events.log("broker_proof_bridge", payload)


def _intelligence_signals_from_event(event: dict[str, Any], payload: dict[str, Any], universe_filter: set[str]) -> list[dict[str, Any]]:
    event_type = str(event.get("event_type") or "")
    timestamp = str(event.get("timestamp") or payload.get("generated_at") or "")
    signals: list[dict[str, Any]] = []

    def allowed(ticker: str | None) -> bool:
        symbol = str(ticker or "").upper()
        return bool(symbol) and (not universe_filter or symbol in universe_filter)

    if event_type == "market_open_observer":
        for row in payload.get("candidate_observations") or []:
            ticker = str(row.get("ticker") or "").upper()
            if not allowed(ticker):
                continue
            flags = row.get("data_flags") or []
            signals.append({
                "source_module": "market_open_observer",
                "ticker": ticker,
                "directional_bias": row.get("direction"),
                "signal_type": "stock_candidate",
                "signal_strength": row.get("score"),
                "confidence_level": row.get("data_confidence") or row.get("confidence"),
                "timestamp": timestamp,
                "data_freshness": row.get("quote_freshness_status") or "unknown",
                "market_regime_context": "scalp_review",
                "supporting_evidence": row,
                "contradicting_evidence": flags,
                "expected_time_horizon": "15m-60m",
                "actionability": "watch_only",
                "noise_risk_rating": "medium" if flags else "low",
            })
    elif event_type == "paper_exploration_run":
        for trial in payload.get("trials") or []:
            ticker = str(trial.get("ticker") or "").upper()
            if not allowed(ticker):
                continue
            signals.append({
                "source_module": "paper_exploration",
                "ticker": ticker,
                "directional_bias": trial.get("stock_direction"),
                "signal_type": trial.get("paper_quality") or trial.get("status"),
                "signal_strength": trial.get("stock_score"),
                "confidence_level": "low",
                "timestamp": timestamp,
                "data_freshness": "paper_trial",
                "market_regime_context": "research_only",
                "supporting_evidence": trial,
                "contradicting_evidence": [trial.get("review_reason")] if trial.get("review_reason") else [],
                "expected_time_horizon": "15m-60m",
                "actionability": "informational",
                "noise_risk_rating": "high",
            })
    elif event_type == "learning_outcome_classification":
        ticker = str(payload.get("ticker") or "").upper()
        if allowed(ticker):
            classification = str(payload.get("classification") or "")
            signals.append({
                "source_module": "learning_engine",
                "ticker": ticker,
                "directional_bias": payload.get("direction"),
                "signal_type": classification,
                "signal_strength": 80 if classification in {"MISSED_MOVE", "BAD_CONTRACT_OR_TOO_STRICT"} else 50,
                "confidence_level": "medium",
                "timestamp": timestamp,
                "data_freshness": "historical_outcome",
                "market_regime_context": "learning",
                "supporting_evidence": payload.get("outcome_summary") or {},
                "contradicting_evidence": [],
                "expected_time_horizon": "future_filter",
                "actionability": "supporting_confirmation",
                "noise_risk_rating": "medium",
            })
    return signals


def _score_intelligence_signal(signal: dict[str, Any]) -> dict[str, Any]:
    strength = _float_or_zero(signal.get("signal_strength"))
    confidence = str(signal.get("confidence_level") or "").lower()
    noise = str(signal.get("noise_risk_rating") or "").lower()
    actionability = str(signal.get("actionability") or "").lower()
    score = min(100.0, max(0.0, strength))
    if confidence == "high":
        score += 10
    elif confidence in {"low", "unknown"}:
        score -= 15
    if noise == "high":
        score -= 25
    elif noise == "medium":
        score -= 8
    if actionability == "actionable":
        score += 10
    elif actionability in {"informational", "watch_only"}:
        score -= 10
    contradicting = [item for item in (signal.get("contradicting_evidence") or []) if item]
    if contradicting:
        score -= min(20, 5 * len(contradicting))
    score = round(max(0.0, min(100.0, score)), 2)
    if score >= 85 and actionability == "actionable":
        final_use = "ACTIONABLE"
    elif score >= 65 and actionability in {"actionable", "supporting_confirmation", "watch_only"}:
        final_use = "SUPPORTING_CONFIRMATION"
    elif score < 35 or noise == "high":
        final_use = "SUPPRESSED_NOISE"
    else:
        final_use = "BACKGROUND_ONLY"
    if "stale" in str(signal.get("data_freshness") or "").lower():
        final_use = "STALE_OR_LOW_CONFIDENCE"
    result = dict(signal)
    result["intelligence_score"] = score
    result["signal_class"] = "contradictory_information" if contradicting else "supporting_confirmation" if final_use in {"ACTIONABLE", "SUPPORTING_CONFIRMATION"} else "background_context"
    result["final_use"] = final_use
    result["escalate"] = bool(final_use == "ACTIONABLE" or result["signal_class"] == "contradictory_information")
    return result


def _event_lane_decision(stock_row: dict[str, Any], review: dict[str, Any] | None, direct_symbol: str) -> dict[str, Any]:
    ticker = str(stock_row.get("ticker") or "").upper()
    direction = str(stock_row.get("direction") or "").lower()
    signals = stock_row.get("key_signals") or {}
    vwap_state = "above" if signals.get("above_vwap") else "below" if signals.get("below_vwap") else "unknown"
    base = {
        "ticker": ticker,
        "stock_direction": direction,
        "stock_score": stock_row.get("score"),
        "relative_volume": signals.get("relative_volume"),
        "vwap_state": vwap_state,
        "stock_setup_quality": (stock_row.get("quality_gates") or {}).get("stock_setup_quality"),
        "stock_status": stock_row.get("status"),
        "why_not_ranked": [],
        "review_only": True,
        "order_allowed": False,
    }
    if ticker == direct_symbol:
        return {
            **base,
            "lane": "DIRECT_IPO_STOCK_REVIEW",
            "rankable_as_options": False,
            "why_not_ranked": ["Direct IPO symbol is stock-review only until options are actually listed and validated by broker snapshot."],
        }
    if ticker in {"SPY", "QQQ", "IWM"} and not review:
        return {
            **base,
            "lane": "INDEX_VOLATILITY_STOCK_REVIEW",
            "rankable_as_options": False,
            "why_not_ranked": ["Index volatility proxy has stock setup, but no small-account options review passed yet."],
        }
    if not review:
        return {
            **base,
            "lane": "STOCK_REVIEW_FALLBACK",
            "rankable_as_options": False,
            "why_not_ranked": ["Stock setup passed, but options review was not run within the review_top_n window."],
        }
    small = review.get("small_account_review") or {}
    selected = small.get("selected_contract") or {}
    option_status = review.get("status")
    small_status = small.get("status")
    option_ready = option_status == "REVIEW_ONLY_OPTIONS_READY" and small_status == "SMALL_ACCOUNT_SCALP_ACCEPTABLE"
    if option_ready:
        return {
            **base,
            "lane": "SYMPATHY_OPTIONS_REVIEW_READY",
            "rankable_as_options": True,
            "option_direction": "call" if direction == "long" else "put",
            "priority_score": small.get("priority_score"),
            "friction_adjusted_score": small.get("friction_adjusted_score"),
            "friction_band": small.get("friction_band"),
            "selected_contract": selected.get("contract_symbol"),
            "ask": selected.get("ask"),
            "max_loss_dollars": selected.get("max_loss_dollars"),
            "spread_pct": selected.get("spread_pct"),
            "dte": selected.get("days_to_expiration"),
            "warnings": review.get("warnings") or small.get("warnings") or [],
            "why_not_ranked": [],
        }
    return {
        **base,
        "lane": "STOCK_REVIEW_FALLBACK",
        "rankable_as_options": False,
        "option_status": option_status,
        "small_account_status": small_status,
        "selected_contract": selected.get("contract_symbol") if selected else None,
        "why_not_ranked": [
            "Stock setup passed, but options candidate did not clear both OPTIONS_CHAIN_ACCEPTABLE and SMALL_ACCOUNT_SCALP_ACCEPTABLE.",
            review.get("reason") or "Options review did not return a rankable small-account contract.",
        ],
        "warnings": review.get("warnings") or small.get("warnings") or [],
    }


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
            "Session risk guard is not SESSION_RISK_BLOCKED.",
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
    account_ref = _float_or_zero(account_value) or 50.0
    latest_readiness = _latest_payload(service_container, "market_readiness")
    latest_harvest = _latest_payload(service_container, "review_harvest")
    latest_followup = _latest_payload(service_container, "harvest_followup")
    latest_learning = _latest_payload(service_container, "learning_summary")
    session_risk = _get_session_risk_guard(service_container, account_ref, None, 2)
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
        "account_value_reference": account_ref,
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
            "session_risk_guard": _compact_event(session_risk),
        },
        "counts": {
            "market_readiness": service_container.events.count("market_readiness"),
            "review_harvest": service_container.events.count("review_harvest"),
            "harvest_followup": service_container.events.count("harvest_followup"),
            "learning_classifications": service_container.events.count("learning_outcome_classification"),
            "review_outcomes": service_container.events.count("review_outcome"),
            "session_risk_guard": service_container.events.count("session_risk_guard"),
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
            "session_playbook": f"/ops/session-playbook?tickers={ticker_query}&account_value={account_ref}",
            "market_readiness": f"/ops/market-readiness?tickers={ticker_query}&max_candidates=25",
            "review_harvest": f"/ops/review-harvest?tickers={ticker_query}&max_candidates=25&review_top_n=8&max_contract_price={service_container.settings.scalp_max_contract_price}",
            "harvest_followup": "/ops/harvest-followup?limit=5&classify=true",
            "session_risk": f"/risk/session?account_value={account_ref}&max_open_positions=2&format=html",
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
            "Session risk guard is not SESSION_RISK_BLOCKED.",
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


def _get_trading_day_launch_checklist(service_container, tickers: list[str] | None, account_value: float, max_candidates: int) -> dict:
    max_candidates = max(1, min(int(max_candidates or 25), 50))
    universe = _resolve_universe(service_container, tickers)
    ticker_query = ",".join(universe)
    account_ref = _float_or_zero(account_value) or 50.0
    session_risk = _get_session_risk_guard(service_container, account_ref, None, 2)
    latest_readiness = _latest_payload(service_container, "market_readiness")
    latest_observer = _latest_payload(service_container, "market_open_observer")
    latest_live_cycle = _latest_payload(service_container, "live_review_cycle")
    latest_manual_action = _latest_payload(service_container, "manual_broker_action")
    latest_checkpoint = _latest_payload(service_container, "journal_checkpoint")
    pending_recheck_required = bool(latest_manual_action and latest_manual_action.get("pending_buy"))
    session_risk_blocked = session_risk.get("status") == "SESSION_RISK_BLOCKED"
    live_candidates = bool((latest_live_cycle or {}).get("ranked_candidates"))
    if pending_recheck_required:
        status = "LAUNCH_PENDING_RECHECK_REQUIRED"
        next_action = "Run the pending-buy recheck before trusting any manually queued buy."
    elif session_risk_blocked:
        status = "LAUNCH_SESSION_RISK_BLOCKED"
        next_action = "Do not add another idea; manage open paper/manual risk or close/log outcomes first."
    elif live_candidates:
        status = "LAUNCH_MANUAL_INSPECTION_READY"
        next_action = "Inspect the top live-cycle candidate in broker, then use manual trade desk with broker-visible fields."
    elif latest_observer and int(latest_observer.get("candidate_count") or 0) > 0:
        status = "LAUNCH_READY_FOR_LIVE_CYCLE"
        next_action = "Run live review cycle; only continue if stock setup and SMALL_ACCOUNT_SCALP_ACCEPTABLE both pass."
    elif latest_readiness:
        status = "LAUNCH_READY_FOR_OBSERVER"
        next_action = "Run market-open observer while spreads stabilize and save evidence."
    else:
        status = "LAUNCH_START_HERE"
        next_action = "Start with health/build checks, then market readiness and market-open observer."

    payload = {
        "status": status,
        "build_version": BUILD_VERSION,
        "mode": "trading_day_launch_checklist",
        "generated_at": utc_now(),
        "universe": universe,
        "account_value_reference": account_ref,
        "max_candidates": max_candidates,
        "next_action": next_action,
        "latest": {
            "session_risk_guard": _compact_event(session_risk),
            "market_readiness": _compact_event(latest_readiness),
            "market_open_observer": _compact_event(latest_observer),
            "live_review_cycle": _compact_event(latest_live_cycle),
            "manual_broker_action": _compact_event(latest_manual_action),
            "journal_checkpoint": _compact_event(latest_checkpoint),
        },
        "counts": {
            "market_readiness": service_container.events.count("market_readiness"),
            "market_open_observer": service_container.events.count("market_open_observer"),
            "observer_followup": service_container.events.count("observer_followup"),
            "live_review_cycle": service_container.events.count("live_review_cycle"),
            "manual_broker_action": service_container.events.count("manual_broker_action"),
            "manual_option_paper_entry": service_container.events.count("manual_option_paper_entry"),
            "manual_option_paper_close": service_container.events.count("manual_option_paper_close"),
            "journal_checkpoint": service_container.events.count("journal_checkpoint"),
            "session_risk_guard": service_container.events.count("session_risk_guard"),
        },
        "launch_sequence": [
            {
                "phase": "Build and safety",
                "go_condition": "Build matches expected version, safety is review-only, and order/cancel capabilities are false.",
                "primary_link": f"/health/full?expected_build_version={BUILD_VERSION}",
                "stop_if": "Wrong build, missing required tools, or any execution capability appears enabled.",
            },
            {
                "phase": "Session risk",
                "go_condition": "Open journaled option risk is below cap and max open positions has not been reached.",
                "primary_link": f"/risk/session?account_value={account_ref}&max_open_positions=2&format=html",
                "stop_if": "Session risk is SESSION_RISK_BLOCKED, hard lockout is reached, or open exposure is already full.",
            },
            {
                "phase": "Opening observation",
                "go_condition": "Market data rows are available and evidence confidence is not LOW across the board.",
                "primary_link": f"/ops/market-open-observer?tickers={ticker_query}&max_candidates={max_candidates}&cadence_minutes=5&format=html",
                "stop_if": "Quote/candle data is blocked, stale during regular market, or no valid rows appear.",
            },
            {
                "phase": "Live review cycle",
                "go_condition": "A candidate passes stock setup, options quality, small-account suitability, friction, and memory checks.",
                "primary_link": f"/ops/live-review-cycle?tickers={ticker_query}&account_value={account_ref}&max_candidates={max_candidates}&review_top_n=8&max_contract_price={service_container.settings.scalp_max_contract_price}&format=html",
                "stop_if": "Result is NO_TRADE_PLAN, data blocked, no eligible candidate, high friction, stale options, or unclear direction.",
            },
            {
                "phase": "Manual broker inspection",
                "go_condition": "Broker-visible contract symbol, bid/ask, volume, OI, DTE, strike, and max loss still match or improve.",
                "primary_link": "/trade/manual-desk",
                "stop_if": "Spread widens, liquidity dries up, setup weakens, or manual preflight is not MANUAL_PREFLIGHT_READY.",
            },
            {
                "phase": "Manual action journal",
                "go_condition": "Any broker-side manual action is logged as user-reported evidence.",
                "primary_link": "/trade/manual-action",
                "stop_if": "A pending buy exists older than 60 seconds without recheck.",
            },
            {
                "phase": "Learning and checkpoint",
                "go_condition": "Observer follow-up, paper ledger, and journal checkpoint are saved after meaningful decisions.",
                "primary_link": "/journal/checkpoint?limit=500&format=json",
                "stop_if": "Do not change rules from a single outcome or without backtesting.",
            },
        ],
        "absolute_no_trade_rules": [
            "No market orders.",
            "No trade from stock setup alone.",
            "No trade from OPTIONS_CHAIN_ACCEPTABLE alone; small-account gate must also pass.",
            "No broker action from this MCP.",
            "No stale pending buy trusted after 60 seconds without recheck.",
            "No new manual idea while session risk is SESSION_RISK_BLOCKED.",
            "No rule changes auto-applied from learning labels.",
        ],
        "action_links": {
            "health_full": f"/health/full?expected_build_version={BUILD_VERSION}",
            "tool_manifest": "/debug/tool-manifest",
            "scan_schema": f"/debug/scan-schema?expected_build_version={BUILD_VERSION}",
            "session_risk": f"/risk/session?account_value={account_ref}&max_open_positions=2&format=html",
            "market_readiness": f"/ops/market-readiness?tickers={ticker_query}&max_candidates={max_candidates}",
            "market_open_observer": f"/ops/market-open-observer?tickers={ticker_query}&max_candidates={max_candidates}&cadence_minutes=5&format=html",
            "live_review_cycle": f"/ops/live-review-cycle?tickers={ticker_query}&account_value={account_ref}&max_candidates={max_candidates}&review_top_n=8&max_contract_price={service_container.settings.scalp_max_contract_price}&format=html",
            "manual_trade_desk": "/trade/manual-desk",
            "manual_action_journal": "/trade/manual-action",
            "pending_recheck": "/trade/pending-recheck",
            "observer_followup": "/ops/observer-followup?limit_observations=3&max_items=20&include_passes=true&classify=true&format=html",
            "paper_ledger": "/paper/options/summary?format=html",
            "journal_checkpoint": "/journal/checkpoint?limit=500&format=json",
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
        "broker_action": False,
        "notes": [
            "This checklist is an operating map, not a trade recommendation.",
            "Use it as the first page tomorrow, then follow links one gate at a time.",
            "PASS remains the default when any data, options, risk, friction, or broker-visible field is unclear.",
        ],
    }
    return service_container.events.log("trading_day_launch_checklist", payload)


def _get_tomorrow_operator_brief(service_container, tickers: list[str] | None, account_value: float, max_candidates: int) -> dict:
    max_candidates = max(1, min(int(max_candidates or 25), 50))
    universe = _resolve_universe(service_container, tickers)
    ticker_query = ",".join(universe)
    account_ref = _float_or_zero(account_value) or 50.0
    contract_cap = service_container.settings.scalp_max_contract_price
    session_risk = _get_session_risk_guard(service_container, account_ref, None, 2)
    paper_ledger = _summarize_manual_option_paper_trades(service_container, 100)
    latest_launch = _latest_payload(service_container, "trading_day_launch_checklist")
    latest_heartbeat = _latest_payload(service_container, "trading_day_heartbeat")
    latest_live_cycle = _latest_payload(service_container, "live_review_cycle")
    latest_manual_action = _latest_payload(service_container, "manual_broker_action")
    latest_checkpoint = _latest_payload(service_container, "journal_checkpoint")
    pending_recheck_required = bool(latest_manual_action and latest_manual_action.get("pending_buy"))
    session_risk_blocked = session_risk.get("status") == "SESSION_RISK_BLOCKED"

    if pending_recheck_required:
        status = "OPERATOR_PENDING_RECHECK_REQUIRED"
        next_action = "Run pending-buy recheck before any new scan or review loop."
    elif session_risk_blocked:
        status = "OPERATOR_SESSION_RISK_BLOCKED"
        next_action = "Manage or close/log open paper/manual exposure before considering another idea."
    else:
        status = "OPERATOR_READY_TO_START"
        next_action = "Open launch, morning autopilot, and day monitor; wait for clean market data before live review."

    action_links = {
        "version": "/version",
        "tools": "/tools",
        "health_full": f"/health/full?expected_build_version={BUILD_VERSION}",
        "debug_schema": f"/debug/scan-schema?expected_build_version={BUILD_VERSION}",
        "launch": f"/ops/trading-day-launch?tickers={ticker_query}&account_value={account_ref}&max_candidates={max_candidates}&format=html",
        "morning_autopilot": f"/ops/morning-autopilot?tickers={ticker_query}&account_value={account_ref}&max_candidates={max_candidates}&format=html",
        "day_monitor": f"/ops/day-monitor?tickers={ticker_query}&account_value={account_ref}&max_candidates={max_candidates}&review_top_n=8&max_contract_price={contract_cap}&format=html",
        "day_alerts": "/ops/day-alerts?limit=50&format=html",
        "session_risk": f"/risk/session?account_value={account_ref}&max_open_positions=2&format=html",
        "live_review_cycle": f"/ops/live-review-cycle?tickers={ticker_query}&account_value={account_ref}&max_candidates={max_candidates}&review_top_n=8&max_contract_price={contract_cap}&format=html",
        "manual_snapshot_form": "/trade/manual-form?format=html",
        "manual_trade_desk": "/trade/manual-desk",
        "manual_action_journal": "/trade/manual-action",
        "pending_recheck": "/trade/pending-recheck",
        "paper_ledger": "/paper/options/summary?format=html",
        "learning_dashboard": "/learning/dashboard",
        "journal_checkpoint": "/journal/checkpoint?limit=500&format=json",
    }
    validation_urls = [
        "/version",
        "/tools",
        f"/health/full?expected_build_version={BUILD_VERSION}",
        f"/debug/scan-schema?expected_build_version={BUILD_VERSION}",
    ]
    payload = {
        "status": status,
        "build_version": BUILD_VERSION,
        "mode": "tomorrow_operator_brief",
        "generated_at": utc_now(),
        "timezone": "America/Chicago",
        "universe": universe,
        "account_value_reference": account_ref,
        "max_candidates": max_candidates,
        "small_account_contract_cap": contract_cap,
        "next_action": next_action,
        "safety": {
            "review_only": True,
            "place_orders": False,
            "market_orders_allowed": False,
            "manual_approval_required": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        },
        "session_risk_guard": _compact_event(session_risk),
        "paper_ledger": {
            "status": paper_ledger.get("status"),
            "entry_count": paper_ledger.get("entry_count"),
            "open_count": paper_ledger.get("open_count"),
            "closed_count": paper_ledger.get("closed_count"),
            "win_rate": paper_ledger.get("win_rate"),
            "total_pnl_dollars": paper_ledger.get("total_pnl_dollars"),
        },
        "latest": {
            "launch": _compact_event(latest_launch),
            "heartbeat": _compact_event(latest_heartbeat),
            "live_review_cycle": _compact_event(latest_live_cycle),
            "manual_broker_action": _compact_event(latest_manual_action),
            "journal_checkpoint": _compact_event(latest_checkpoint),
        },
        "morning_sequence": [
            {
                "step": "1. Confirm deployment",
                "target_time_ct": "Before open",
                "link": action_links["health_full"],
                "pass_condition": "OK and build matches.",
            },
            {
                "step": "2. Open launch page",
                "target_time_ct": "Before open",
                "link": action_links["launch"],
                "pass_condition": "No pending recheck and session risk not blocked.",
            },
            {
                "step": "3. Run morning autopilot",
                "target_time_ct": "Before open",
                "link": action_links["morning_autopilot"],
                "pass_condition": "Data/readiness state is clear enough to observe.",
            },
            {
                "step": "4. Leave day monitor open",
                "target_time_ct": "Market hours",
                "link": action_links["day_monitor"],
                "pass_condition": "Heartbeat cadence runs without execution capability.",
            },
            {
                "step": "5. Use live cycle only after stabilization",
                "target_time_ct": "After opening noise",
                "link": action_links["live_review_cycle"],
                "pass_condition": "Stock setup, options quality, small-account gate, and session risk all pass.",
            },
            {
                "step": "6. Manual desk only with broker-visible fields",
                "target_time_ct": "Only if candidate survives",
                "link": action_links["manual_trade_desk"],
                "pass_condition": "Manual desk ready and session risk clear.",
            },
            {
                "step": "7. Log and checkpoint",
                "target_time_ct": "After any decision",
                "link": action_links["journal_checkpoint"],
                "pass_condition": "Paper/manual action and learning evidence saved.",
            },
        ],
        "session_schedule_ct": [
            {"time": "08:20-08:30", "focus": "Build, safety, and session-risk check only."},
            {"time": "08:30-08:50", "focus": "Observe opening volatility; do not force options reviews."},
            {"time": "08:50-10:15", "focus": "Run live review cycle only when data, spreads, and direction are clean."},
            {"time": "10:15-12:30", "focus": "Lower activity; keep monitor/alerts open and log misses."},
            {"time": "12:30-14:15", "focus": "Afternoon manual-review window if gates are clean."},
            {"time": "After close", "focus": "Review outcomes, classify mistakes, checkpoint journal."},
        ],
        "chatgpt_connector_fallback": {
            "short_status": "If ChatGPT says the connector is unavailable, use public endpoints instead of treating the app as broken.",
            "validation_urls": validation_urls,
            "prompt": (
                "Living Screener MCP may be connected but the callable namespace may not be exposed in this turn. "
                "First try get_version and get_safety_config. If unavailable, use public fallback endpoints /version, /tools, "
                f"/health/full?expected_build_version={BUILD_VERSION}, and /debug/scan-schema?expected_build_version={BUILD_VERSION}. "
                "Report endpoint/runtime failure only as endpoint access failed from this runtime. Do not create a trade plan unless explicitly requested and safety gates pass."
            ),
        },
        "manual_trade_gate": [
            "Build and safety confirmed.",
            "No pending buy older than 60 seconds without recheck.",
            "Session risk guard is not SESSION_RISK_BLOCKED.",
            "Live review cycle status is LIVE_CYCLE_CANDIDATES_READY.",
            "Candidate is REVIEW_ONLY_OPTIONS_READY.",
            "Small-account gate is SMALL_ACCOUNT_SCALP_ACCEPTABLE.",
            "Broker-visible snapshot matches or improves the reviewed contract.",
            "Manual trade desk returns MANUAL_TRADE_DESK_READY.",
            "Limit-only discipline; no market orders.",
            "Any broker action is manual/outside MCP and must be logged afterward.",
        ],
        "absolute_no_trade_rules": [
            "No broker action from this MCP.",
            "No market orders.",
            "No stock-setup-only trades.",
            "No OPTIONS_CHAIN_ACCEPTABLE-only trades.",
            "No new idea while session risk is blocked.",
            "No stale pending buy trusted after 60 seconds.",
            "No rule changes from one outcome or without backtesting.",
        ],
        "action_links": action_links,
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "broker_action": False,
        "notes": [
            "Operator brief is a human runbook; it does not run a scan or create a trade plan.",
            "Use this as the first page tomorrow so every next step goes through the same safety gates.",
            "Accuracy comes before opportunity count; PASS remains correct when any required evidence is missing.",
        ],
    }
    return service_container.events.log("tomorrow_operator_brief", payload)


def _run_go_live_rehearsal(
    service_container,
    tickers: list[str] | None,
    account_value: float,
    max_candidates: int,
    include_market_check: bool = False,
) -> dict:
    max_candidates = max(1, min(int(max_candidates or 25), 50))
    universe = _resolve_universe(service_container, tickers)
    ticker_query = ",".join(universe)
    account_ref = _float_or_zero(account_value) or 50.0
    brief = _get_tomorrow_operator_brief(service_container, universe, account_ref, max_candidates)
    market_readiness = _market_readiness_check(service_container, universe, max_candidates) if include_market_check else None
    session_risk = brief.get("session_risk_guard") or {}
    operator_status = str(brief.get("status") or "")
    blocking_reasons: list[str] = []
    warnings: list[str] = []

    if operator_status == "OPERATOR_PENDING_RECHECK_REQUIRED":
        blocking_reasons.append("Pending buy recheck is required before any new review loop.")
    if operator_status == "OPERATOR_SESSION_RISK_BLOCKED" or session_risk.get("status") == "SESSION_RISK_BLOCKED":
        blocking_reasons.append("Session risk guard is blocking new manual option ideas.")
    if include_market_check and market_readiness:
        readiness_status = str(market_readiness.get("status") or "")
        if readiness_status == "MARKET_DATA_BLOCKED":
            blocking_reasons.append("Market readiness reports blocked quote/candle data.")
        elif readiness_status == "MARKET_READINESS_UNKNOWN":
            warnings.append("Market readiness is unknown; use observation mode until data improves.")
        elif readiness_status == "MARKET_DATA_READY_NO_CANDIDATES":
            warnings.append("Market data is usable but no stock candidates are present.")

    if blocking_reasons:
        status = "GO_LIVE_REHEARSAL_BLOCKED"
        next_action = "Fix the blocking item before starting tomorrow's live review workflow."
    elif warnings:
        status = "GO_LIVE_REHEARSAL_CAUTION"
        next_action = "Open the operator brief and day monitor; do not force trades while cautions remain."
    else:
        status = "GO_LIVE_REHEARSAL_READY"
        next_action = "Deploy/validate this build, then start tomorrow at the operator brief and day monitor."

    payload = {
        "status": status,
        "build_version": BUILD_VERSION,
        "mode": "go_live_rehearsal",
        "generated_at": utc_now(),
        "universe": universe,
        "account_value_reference": account_ref,
        "max_candidates": max_candidates,
        "include_market_check": bool(include_market_check),
        "next_action": next_action,
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
        "safety": {
            "review_only": True,
            "place_orders": False,
            "market_orders_allowed": False,
            "manual_approval_required": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        },
        "operator_brief": {
            "status": brief.get("status"),
            "next_action": brief.get("next_action"),
            "session_risk_status": session_risk.get("status"),
            "paper_open_count": (brief.get("paper_ledger") or {}).get("open_count"),
        },
        "market_readiness": _compact_autopilot_result(market_readiness) if market_readiness else None,
        "required_live_urls": [
            {"label": "Root operator brief", "url": "/", "expected": "HTML page with Tomorrow Operator Brief."},
            {"label": "Version", "url": "/version", "expected": f"build_version {BUILD_VERSION}."},
            {"label": "Tools", "url": "/tools", "expected": "Includes run_go_live_rehearsal and get_tomorrow_operator_brief."},
            {"label": "Full health", "url": f"/health/full?expected_build_version={BUILD_VERSION}", "expected": "OK, not BUILD_MISMATCH."},
            {"label": "Debug schema", "url": f"/debug/scan-schema?expected_build_version={BUILD_VERSION}", "expected": "Includes rehearsal and operator brief previews."},
            {"label": "Tomorrow brief", "url": f"/ops/tomorrow-brief?tickers={ticker_query}&account_value={account_ref}&format=html", "expected": "Readable operator page."},
            {"label": "Go-live rehearsal", "url": f"/ops/go-live-rehearsal?tickers={ticker_query}&account_value={account_ref}&format=html", "expected": "GO_LIVE_REHEARSAL_READY or clear blocking reasons."},
            {"label": "Manual snapshot form", "url": "/trade/manual-form?format=html", "expected": "Readable form for broker-visible option fields."},
        ],
        "tomorrow_open_tabs": [
            {"label": "Operator brief", "url": f"/ops/tomorrow-brief?tickers={ticker_query}&account_value={account_ref}&format=html"},
            {"label": "Day monitor", "url": f"/ops/day-monitor?tickers={ticker_query}&account_value={account_ref}&max_candidates={max_candidates}&format=html"},
            {"label": "Day alerts", "url": "/ops/day-alerts?limit=50&format=html"},
            {"label": "Session risk", "url": f"/risk/session?account_value={account_ref}&max_open_positions=2&format=html"},
            {"label": "Manual snapshot form", "url": "/trade/manual-form?format=html"},
            {"label": "Paper ledger", "url": "/paper/options/summary?format=html"},
        ],
        "manual_trade_gate": brief.get("manual_trade_gate") or [],
        "absolute_no_trade_rules": brief.get("absolute_no_trade_rules") or [],
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "broker_action": False,
        "notes": [
            "Rehearsal checks operator readiness and optional market data readiness; it does not rank options or create a trade plan.",
            "Use include_market_check=true only when you want a fresh market-readiness scan as part of the rehearsal.",
            "A READY rehearsal means the workflow can start; it is not a trade recommendation.",
        ],
    }
    return service_container.events.log("go_live_rehearsal", payload)


def _market_phase(force_phase: str | None = None) -> dict[str, Any]:
    forced = str(force_phase or "").strip().lower()
    allowed = {"premarket", "opening", "active", "late", "afterhours", "closed", "offhours"}
    now_utc = datetime.now(UTC)
    now_et = now_utc.astimezone(ZoneInfo("America/New_York"))
    if forced in allowed:
        phase = "offhours" if forced == "closed" else forced
        forced_phase = True
    elif now_et.weekday() >= 5:
        phase = "offhours"
        forced_phase = False
    else:
        minutes = now_et.hour * 60 + now_et.minute
        if minutes < 9 * 60 + 30:
            phase = "premarket"
        elif minutes < 10 * 60:
            phase = "opening"
        elif minutes < 15 * 60 + 30:
            phase = "active"
        elif minutes < 16 * 60:
            phase = "late"
        else:
            phase = "afterhours"
        forced_phase = False
    return {
        "phase": phase,
        "forced": forced_phase,
        "now_utc": now_utc.isoformat().replace("+00:00", "Z"),
        "now_et": now_et.isoformat(),
    }


def _heartbeat_next_refresh_seconds(phase: str, pending_recheck_required: bool) -> int:
    if pending_recheck_required:
        return 60
    if phase == "opening":
        return 300
    if phase in {"active", "late"}:
        return 300
    if phase == "premarket":
        return 600
    return 1800


def _run_trading_day_heartbeat(
    service_container,
    tickers: list[str] | None,
    account_value: float,
    max_candidates: int,
    review_top_n: int,
    max_contract_price: float | None,
    force_phase: str | None = None,
) -> dict:
    max_candidates = max(1, min(int(max_candidates or 25), 50))
    review_top_n = max(1, min(int(review_top_n or 8), 20))
    account_value = _float_or_zero(account_value) or 50.0
    max_contract_price = max_contract_price if max_contract_price is not None else service_container.settings.scalp_max_contract_price
    universe = _resolve_universe(service_container, tickers)
    ticker_query = ",".join(universe)
    phase_info = _market_phase(force_phase)
    phase = str(phase_info.get("phase") or "offhours")
    latest_manual_action = _latest_payload(service_container, "manual_broker_action")
    pending_recheck_required = bool(latest_manual_action and latest_manual_action.get("pending_buy"))
    operation = "none"
    operation_result: dict[str, Any] | None = None
    followup_result: dict[str, Any] | None = None
    if pending_recheck_required:
        status = "HEARTBEAT_PENDING_RECHECK_REQUIRED"
        next_action = "Run pending-buy recheck before any new review cycle."
        operation = "pending_recheck_required"
    elif phase == "premarket":
        operation_result = _market_readiness_check(service_container, universe, max_candidates)
        operation = "market_readiness"
        status = "HEARTBEAT_PREMARKET_READY"
        next_action = "Keep readiness checks warm; start market-open observer when regular-session data begins."
    elif phase == "opening":
        operation_result = _run_market_open_observer(service_container, universe, max_candidates, 5)
        operation = "market_open_observer"
        status = "HEARTBEAT_OBSERVER_RECORDED"
        next_action = "Keep observing until spreads/data stabilize, then move to live review cycle only if candidates persist."
    elif phase in {"active", "late"}:
        operation_result = _run_live_review_cycle(service_container, universe, account_value, max_candidates, review_top_n, max_contract_price, include_followup=False)
        operation = "live_review_cycle"
        ranked = operation_result.get("ranked_candidates") or []
        if operation_result.get("status") == "LIVE_CYCLE_SESSION_RISK_BLOCKED":
            status = "HEARTBEAT_SESSION_RISK_BLOCKED"
            next_action = "Candidate exists, but session risk blocks adding exposure. Manage/log open risk first."
        elif ranked and operation_result.get("manual_preflight_required"):
            status = "HEARTBEAT_MANUAL_REVIEW_READY"
            next_action = "Inspect top ranked candidate in broker and use manual trade desk with broker-visible fields."
        elif operation_result.get("status") in {"LIVE_CYCLE_DATA_BLOCKED", "LIVE_CYCLE_NOT_READY"}:
            status = "HEARTBEAT_DATA_BLOCKED"
            next_action = "Do not review contracts; fix data/readiness or wait for cleaner market data."
        else:
            status = "HEARTBEAT_NO_TRADE_PLAN"
            next_action = "No eligible small-account scalp candidate; continue cadence without forcing a setup."
    else:
        operation_result = _run_observer_followup(service_container, 5, 30, True, True)
        operation = "observer_followup"
        followup_result = operation_result
        status = "HEARTBEAT_LEARNING_REVIEW_READY"
        next_action = "Review learning labels, export a journal checkpoint, and avoid live options decisions while closed."

    refresh_seconds = _heartbeat_next_refresh_seconds(phase, pending_recheck_required)
    payload = {
        "status": status,
        "build_version": BUILD_VERSION,
        "mode": "trading_day_heartbeat",
        "generated_at": utc_now(),
        "phase": phase_info,
        "universe": universe,
        "account_value_reference": account_value,
        "max_candidates": max_candidates,
        "review_top_n": review_top_n,
        "max_contract_price": max_contract_price,
        "operation": operation,
        "operation_status": (operation_result or {}).get("status"),
        "operation_result": _compact_event(operation_result),
        "followup_result": _compact_event(followup_result),
        "pending_recheck_required": pending_recheck_required,
        "latest_manual_action": _compact_event(latest_manual_action),
        "next_action": next_action,
        "next_refresh_seconds": refresh_seconds,
        "action_links": {
            "self": f"/ops/day-heartbeat?tickers={ticker_query}&account_value={account_value}&max_candidates={max_candidates}&review_top_n={review_top_n}&max_contract_price={max_contract_price}&format=html",
            "launch": f"/ops/trading-day-launch?tickers={ticker_query}&account_value={account_value}&max_candidates={max_candidates}&format=html",
            "market_open_observer": f"/ops/market-open-observer?tickers={ticker_query}&max_candidates={max_candidates}&cadence_minutes=5&format=html",
            "live_review_cycle": f"/ops/live-review-cycle?tickers={ticker_query}&account_value={account_value}&max_candidates={max_candidates}&review_top_n={review_top_n}&max_contract_price={max_contract_price}&format=html",
            "manual_trade_desk": "/trade/manual-desk",
            "pending_recheck": "/trade/pending-recheck",
            "observer_followup": "/ops/observer-followup?limit_observations=5&max_items=30&include_passes=true&classify=true&format=html",
            "journal_checkpoint": "/journal/checkpoint?limit=500&format=json",
        },
        "absolute_no_trade_rules": [
            "No market orders.",
            "No broker action from this MCP.",
            "No trade from the heartbeat alone; use live review cycle plus manual trade desk.",
            "No stale pending buy trusted after 60 seconds without recheck.",
            "No rule changes auto-applied from heartbeat learning labels.",
        ],
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "broker_action": False,
        "notes": [
            "Heartbeat is a cadence helper for monitoring and learning, not a trade recommendation.",
            "It runs exactly one safe workflow step based on market phase.",
            "Manual broker inspection still requires broker-visible bid/ask, volume, OI, DTE, strike, and max loss.",
        ],
    }
    return service_container.events.log("trading_day_heartbeat", payload)


def _summarize_trading_day_alerts(service_container, limit: int = 50) -> dict:
    limit = max(1, min(int(limit or 50), 200))
    heartbeats = service_container.events.recent("trading_day_heartbeat", limit)
    live_cycles = service_container.events.recent("live_review_cycle", limit)
    manual_actions = service_container.events.recent("manual_broker_action", limit)
    checkpoints = service_container.events.recent("journal_checkpoint_export", 5)
    alerts: list[dict[str, Any]] = []
    latest_manual = manual_actions[0] if manual_actions else None
    latest_manual_payload = (latest_manual or {}).get("payload") or {}
    if latest_manual_payload.get("pending_buy"):
        alerts.append(
            {
                "priority": 100,
                "level": "URGENT",
                "type": "PENDING_BUY_RECHECK",
                "title": "Pending buy requires 60-second recheck",
                "timestamp": latest_manual.get("timestamp"),
                "source_event_id": latest_manual.get("id"),
                "status": latest_manual_payload.get("status"),
                "next_action": "Open /trade/pending-recheck before trusting or replacing any queued buy.",
                "link": "/trade/pending-recheck",
            }
        )

    for event in heartbeats[:limit]:
        payload = event.get("payload") or {}
        status = payload.get("status")
        if status == "HEARTBEAT_MANUAL_REVIEW_READY":
            top = _extract_alert_candidate(payload)
            ticker = top.get("ticker")
            contract = top.get("contract_symbol")
            direction = top.get("direction")
            alerts.append(
                {
                    "priority": 90,
                    "level": "REVIEW",
                    "type": "MANUAL_REVIEW_READY",
                    "title": _candidate_alert_title("Heartbeat found a candidate ready for manual broker inspection", ticker, direction, contract),
                    "timestamp": event.get("timestamp"),
                    "source_event_id": event.get("id"),
                    "status": status,
                    "ticker": ticker,
                    "direction": direction,
                    "contract_symbol": contract,
                    "candidate_status": top.get("status"),
                    "is_current": _alert_matches_latest_event(event, heartbeats),
                    "age_bucket": _alert_age_bucket(event.get("timestamp")),
                    "next_action": payload.get("next_action"),
                    "link": (payload.get("action_links") or {}).get("manual_trade_desk") or "/trade/manual-desk",
                }
            )
        elif status in {"HEARTBEAT_DATA_BLOCKED", "HEARTBEAT_PENDING_RECHECK_REQUIRED"}:
            alerts.append(
                {
                    "priority": 80 if status == "HEARTBEAT_PENDING_RECHECK_REQUIRED" else 70,
                    "level": "BLOCKED" if status == "HEARTBEAT_DATA_BLOCKED" else "URGENT",
                    "type": status,
                    "title": "Heartbeat cannot safely continue the normal review cadence",
                    "timestamp": event.get("timestamp"),
                    "source_event_id": event.get("id"),
                    "status": status,
                    "next_action": payload.get("next_action"),
                    "link": (payload.get("action_links") or {}).get("pending_recheck") or "/ops/day-monitor",
                }
            )
        elif status == "HEARTBEAT_LEARNING_REVIEW_READY":
            alerts.append(
                {
                    "priority": 30,
                    "level": "LEARNING",
                    "type": "LEARNING_REVIEW_READY",
                    "title": "Learning follow-up is ready",
                    "timestamp": event.get("timestamp"),
                    "source_event_id": event.get("id"),
                    "status": status,
                    "next_action": payload.get("next_action"),
                    "link": (payload.get("action_links") or {}).get("observer_followup") or "/ops/observer-followup?format=html",
                }
            )

    for event in live_cycles[:limit]:
        payload = event.get("payload") or {}
        ranked = payload.get("ranked_candidates") or []
        if ranked:
            top = ranked[0] if isinstance(ranked[0], dict) else {}
            ticker = top.get("ticker")
            contract = top.get("selected_contract") or top.get("contract_symbol")
            direction = top.get("direction")
            alerts.append(
                {
                    "priority": 85,
                    "level": "REVIEW",
                    "type": "LIVE_CYCLE_CANDIDATE",
                    "title": _candidate_alert_title("Live review cycle has ranked candidate", ticker, direction, contract),
                    "timestamp": event.get("timestamp"),
                    "source_event_id": event.get("id"),
                    "status": payload.get("status"),
                    "ticker": ticker,
                    "direction": direction,
                    "contract_symbol": contract,
                    "candidate_status": top.get("status"),
                    "is_current": _alert_matches_latest_event(event, live_cycles),
                    "age_bucket": _alert_age_bucket(event.get("timestamp")),
                    "next_action": "Use broker-visible fields with /trade/manual-desk before any manual action.",
                    "link": "/trade/manual-desk",
                }
            )

    if not checkpoints:
        alerts.append(
            {
                "priority": 20,
                "level": "REMINDER",
                "type": "CHECKPOINT_NOT_EXPORTED",
                "title": "No recent journal checkpoint export found",
                "timestamp": None,
                "source_event_id": None,
                "status": "CHECKPOINT_SUGGESTED",
                "next_action": "Export /journal/checkpoint after meaningful scan, review, paper, or learning events.",
                "link": "/journal/checkpoint?limit=500&format=json",
            }
        )

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any]] = set()
    for alert in sorted(alerts, key=lambda item: (int(item.get("priority") or 0), str(item.get("timestamp") or "")), reverse=True):
        key = (alert.get("type"), alert.get("source_event_id"), alert.get("ticker"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(alert)

    top_level = "QUIET"
    if any(alert.get("level") == "URGENT" for alert in deduped):
        top_level = "URGENT"
    elif any(alert.get("level") == "REVIEW" for alert in deduped):
        top_level = "REVIEW"
    elif any(alert.get("level") == "BLOCKED" for alert in deduped):
        top_level = "BLOCKED"
    elif any(alert.get("level") in {"LEARNING", "REMINDER"} for alert in deduped):
        top_level = "INFO"

    if top_level == "URGENT":
        status = "ALERTS_REQUIRE_ACTION"
        next_action = "Handle urgent alert before continuing scans or manual review."
    elif top_level == "REVIEW":
        status = "ALERTS_MANUAL_REVIEW_READY"
        next_action = "Inspect the review alert, then use manual trade desk with broker-visible fields."
    elif top_level == "BLOCKED":
        status = "ALERTS_BLOCKED"
        next_action = "Resolve data/pending-order blockage before continuing."
    elif top_level == "INFO":
        status = "ALERTS_INFORMATIONAL"
        next_action = "Review learning/checkpoint reminders when convenient."
    else:
        status = "ALERTS_QUIET"
        next_action = "Continue day monitor cadence; no attention alert is active."

    payload = {
        "status": status,
        "build_version": BUILD_VERSION,
        "mode": "trading_day_alerts",
        "generated_at": utc_now(),
        "top_level": top_level,
        "alert_count": len(deduped),
        "alerts": deduped[:limit],
        "latest": {
            "heartbeat": _compact_event(_latest_payload(service_container, "trading_day_heartbeat")),
            "live_review_cycle": _compact_event(_latest_payload(service_container, "live_review_cycle")),
            "manual_broker_action": _compact_event(_latest_payload(service_container, "manual_broker_action")),
            "journal_checkpoint_export": _compact_event(_latest_payload(service_container, "journal_checkpoint_export")),
        },
        "next_action": next_action,
        "action_links": {
            "day_monitor": "/ops/day-monitor?format=html",
            "manual_trade_desk": "/trade/manual-desk",
            "pending_recheck": "/trade/pending-recheck",
            "journal_checkpoint": "/journal/checkpoint?limit=500&format=json",
            "learning_dashboard": "/learning/dashboard",
        },
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "broker_action": False,
        "notes": [
            "Alerts summarize existing review-only journal events; they do not run broker actions.",
            "Manual review alerts still require broker-visible inspection and manual trade desk preflight.",
            "Only alerts marked current should be treated as live review focus; stale alerts are for learning/history.",
            "Checkpoint reminders preserve learning evidence but are not execution records.",
        ],
    }
    return service_container.events.log("trading_day_alert_summary", payload)


def _extract_alert_candidate(payload: dict[str, Any]) -> dict[str, Any]:
    operation_result = payload.get("operation_result") if isinstance(payload.get("operation_result"), dict) else {}
    ranked = operation_result.get("ranked_candidates") or payload.get("ranked_candidates") or []
    if ranked and isinstance(ranked[0], dict):
        top = dict(ranked[0])
        top["contract_symbol"] = top.get("selected_contract") or top.get("contract_symbol")
        return top
    harvest = operation_result.get("harvest") if isinstance(operation_result.get("harvest"), dict) else {}
    ranked = harvest.get("ranked_candidates") or []
    if ranked and isinstance(ranked[0], dict):
        top = dict(ranked[0])
        top["contract_symbol"] = top.get("selected_contract") or top.get("contract_symbol")
        return top
    return {}


def _candidate_alert_title(prefix: str, ticker: Any, direction: Any, contract: Any) -> str:
    parts = [str(prefix).strip()]
    if ticker:
        parts.append(str(ticker).upper())
    if direction:
        parts.append(str(direction).upper())
    if contract:
        parts.append(str(contract))
    return " - ".join(part for part in parts if part)


def _alert_matches_latest_event(event: dict[str, Any], events: list[dict[str, Any]]) -> bool:
    if not events:
        return False
    return event.get("id") == events[0].get("id")


def _alert_age_bucket(timestamp: Any) -> str:
    if not timestamp:
        return "unknown"
    try:
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        minutes = (datetime.now(UTC) - parsed.astimezone(UTC)).total_seconds() / 60
    except Exception:
        return "unknown"
    if minutes <= 5:
        return "current_0_5m"
    if minutes <= 15:
        return "recent_5_15m"
    return "stale_over_15m"


def _run_morning_readiness_autopilot(service_container, tickers: list[str] | None, account_value: float, max_candidates: int) -> dict:
    max_candidates = max(1, min(int(max_candidates or 25), 50))
    universe = _resolve_universe(service_container, tickers)
    account_ref = _float_or_zero(account_value) or 50.0
    session_risk = _get_session_risk_guard(service_container, account_ref, None, 2)
    readiness = _market_readiness_check(service_container, universe, max_candidates)
    playbook = _get_market_session_playbook(service_container, universe, account_value)
    command_center = _get_ops_command_center(service_container, universe, account_value)
    paper_ledger = _summarize_manual_option_paper_trades(service_container, 100)
    readiness_status = readiness.get("status")
    command_status = command_center.get("status")
    if session_risk.get("status") == "SESSION_RISK_BLOCKED":
        status = "AUTOPILOT_SESSION_RISK_BLOCKED"
        next_action = "Manage open paper/manual option exposure before adding another idea."
    elif readiness_status == "MARKET_DATA_BLOCKED":
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
        "account_value_reference": account_ref,
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
        "session_risk_guard": _compact_event(session_risk),
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
            "session_risk": f"/risk/session?account_value={account_ref}&max_open_positions=2&format=html",
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
            "Session risk must not be blocked before adding any new manual idea.",
            "Use the paper ledger to record manual/paper outcomes so the mistake engine can learn after the fact.",
        ],
    }
    return service_container.events.log("morning_readiness_autopilot", payload)


def _run_autonomous_morning_scan(
    service_container,
    tickers: list[str] | None,
    account_value: float,
    max_candidates: int,
    review_top_n: int,
    max_contract_price: float | None,
    force_phase: str | None,
    catalyst_top_n: int,
) -> dict:
    max_candidates = max(1, min(int(max_candidates or 25), 50))
    review_top_n = max(1, min(int(review_top_n or 8), 20))
    catalyst_top_n = max(0, min(int(catalyst_top_n or 0), 12))
    account_ref = _float_or_zero(account_value) or 50.0
    universe = _resolve_universe(service_container, tickers)
    ticker_query = ",".join(universe)
    phase_info = _market_phase(force_phase)
    phase = str(phase_info.get("phase") or "offhours")
    effective_contract_cap = max_contract_price
    if effective_contract_cap is None:
        effective_contract_cap = service_container.settings.scalp_max_contract_price

    truth = service_container.market_truth.truth_source_status()
    health = service_container.market_truth.check_market_data_health(universe, min(len(universe), 12) or 1)
    catalysts = [
        service_container.market_truth.get_catalyst_context(symbol, 3, 7)
        for symbol in universe[:catalyst_top_n]
    ]
    catalyst_blocks = [
        {
            "ticker": item.get("ticker"),
            "status": item.get("status"),
            "blocking_reasons": item.get("blocking_reasons") or [],
            "risk_items": item.get("risk_items") or [],
        }
        for item in catalysts
        if item.get("status") != "CATALYST_CONTEXT_CLEAR"
    ]

    heartbeat = _run_trading_day_heartbeat(
        service_container,
        universe,
        account_ref,
        max_candidates,
        review_top_n,
        effective_contract_cap,
        force_phase,
    )
    heartbeat_status = heartbeat.get("status")
    health_status = health.get("status")
    truth_cash_ready = bool((truth.get("cash_readiness") or {}).get("cash_ready"))
    health_cash_ready = bool(health.get("cash_ready"))
    has_catalyst_block = bool(catalyst_blocks)

    if heartbeat_status == "HEARTBEAT_PENDING_RECHECK_REQUIRED":
        status = "AUTONOMOUS_PENDING_RECHECK_REQUIRED"
        next_action = "Stop new scans until the pending buy is rechecked after 60 seconds."
    elif phase in {"premarket", "opening", "active", "late"} and health_status == "MARKET_DATA_HEALTH_BLOCKED":
        status = "AUTONOMOUS_DATA_BLOCKED"
        next_action = "Keep the loop alive, but do not rank options or permit manual cash review until market data health clears."
    elif has_catalyst_block:
        status = "AUTONOMOUS_CATALYST_REVIEW_REQUIRED"
        next_action = "Review catalyst blocks before trusting any candidate from the affected symbols."
    elif heartbeat_status == "HEARTBEAT_MANUAL_REVIEW_READY":
        status = "AUTONOMOUS_MANUAL_REVIEW_READY"
        next_action = "Manually inspect the top candidate in broker and use manual trade desk with fresh broker-visible fields."
    elif phase == "premarket":
        status = "AUTONOMOUS_PREMARKET_OBSERVING"
        next_action = "Continue premarket readiness scans; do not review options until regular-session data and spreads are usable."
    elif phase == "opening":
        status = "AUTONOMOUS_OPENING_OBSERVER_ACTIVE"
        next_action = "Keep recording evidence during the opening window; avoid early spread traps."
    elif phase in {"active", "late"}:
        status = "AUTONOMOUS_ACTIVE_SCAN_RUNNING"
        next_action = "Continue live review cycles; only escalate candidates that pass stock, small-account, risk, catalyst, and broker-snapshot gates."
    else:
        status = "AUTONOMOUS_OFFHOURS_LEARNING"
        next_action = "Use observer follow-up and learning summaries while regular-session options liquidity is unavailable."

    refresh_seconds = int(heartbeat.get("next_refresh_seconds") or _heartbeat_next_refresh_seconds(phase, False))
    payload = {
        "status": status,
        "schema_version": "autonomous_morning_scan_v1",
        "build_version": BUILD_VERSION,
        "mode": "autonomous_morning_scan",
        "generated_at": utc_now(),
        "phase": phase_info,
        "universe": universe,
        "account_value_reference": account_ref,
        "max_candidates": max_candidates,
        "review_top_n": review_top_n,
        "max_contract_price_used": effective_contract_cap,
        "truth_source": _compact_event(truth),
        "market_data_health": _compact_event(health),
        "catalyst_context": {
            "checked_count": len(catalysts),
            "clear_count": sum(1 for item in catalysts if item.get("status") == "CATALYST_CONTEXT_CLEAR"),
            "blocked_or_unavailable_count": len(catalyst_blocks),
            "blocks": catalyst_blocks,
        },
        "heartbeat": _compact_event(heartbeat),
        "cash_readiness": {
            "truth_cash_ready": truth_cash_ready,
            "market_data_cash_ready": health_cash_ready,
            "catalyst_blocks_clear": not has_catalyst_block,
            "manual_broker_snapshot_still_required_for_options": True,
            "autonomous_cash_trading_allowed": False,
        },
        "next_action": next_action,
        "next_refresh_seconds": refresh_seconds,
        "action_links": {
            "self": f"/ops/autonomous-morning-scan?tickers={ticker_query}&account_value={account_ref}&max_candidates={max_candidates}&review_top_n={review_top_n}&max_contract_price={effective_contract_cap}&catalyst_top_n={catalyst_top_n}&format=html",
            "truth_source": "/truth/source-status",
            "market_data_health": f"/market/data-health?tickers={ticker_query}&max_tickers=12",
            "day_heartbeat": f"/ops/day-heartbeat?tickers={ticker_query}&account_value={account_ref}&max_candidates={max_candidates}&review_top_n={review_top_n}&max_contract_price={effective_contract_cap}&format=html",
            "live_review_cycle": f"/ops/live-review-cycle?tickers={ticker_query}&account_value={account_ref}&max_candidates={max_candidates}&review_top_n={review_top_n}&max_contract_price={effective_contract_cap}&format=html",
            "manual_trade_desk": "/trade/manual-desk",
            "journal_checkpoint": "/journal/checkpoint?limit=500&format=json",
        },
        "hard_stops": [
            "No broker order can be placed, modified, submitted, simulated, or canceled by this MCP.",
            "No market orders.",
            "No manual cash review while market data health is blocked.",
            "No manual cash review on symbols with unresolved catalyst blocks.",
            "No options cash review without fresh broker-visible bid, ask, volume, open interest, DTE, strike, and max loss.",
            "No stale pending buy trusted after 60 seconds without recheck.",
        ],
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "broker_action": False,
        "notes": [
            "Autonomous means repeated review-only observation and logging, not autonomous trading.",
            "Each call runs one safe phase-aware scan cycle and returns the next refresh interval.",
            "Use a browser auto-refresh tab, uptime monitor, or external scheduler to call this endpoint repeatedly.",
        ],
    }
    return service_container.events.log("autonomous_morning_scan", payload)


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
    universe = _resolve_universe(service_container, tickers)
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
    top_selected = ((ranked_candidates[0] or {}).get("selected_contract") or {}) if ranked_candidates else {}
    proposed_risk = _float_or_zero(top_selected.get("max_loss_dollars"))
    session_risk = _get_session_risk_guard(service_container, account_value, proposed_risk if proposed_risk > 0 else None, 2)
    session_risk_blocked = session_risk.get("status") == "SESSION_RISK_BLOCKED"
    if readiness.get("status") == "MARKET_DATA_BLOCKED":
        status = "LIVE_CYCLE_DATA_BLOCKED"
        next_action = "Do not review options; wait for clean quote/candle data."
    elif not harvest:
        status = "LIVE_CYCLE_STANDBY"
        next_action = "Rerun readiness near the next market window."
    elif ranked_candidates and session_risk_blocked:
        status = "LIVE_CYCLE_SESSION_RISK_BLOCKED"
        next_action = "Candidate exists, but session risk blocks adding exposure. Manage/log open risk first."
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
        "session_risk_guard": _compact_event(session_risk),
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
        "manual_preflight_required": bool(ranked_candidates) and not session_risk_blocked,
        "manual_trade_gate": [
            "Live review cycle status is LIVE_CYCLE_CANDIDATES_READY.",
            "Candidate status is REVIEW_ONLY_OPTIONS_READY.",
            "Small-account gate is SMALL_ACCOUNT_SCALP_ACCEPTABLE.",
            "Session risk guard is not SESSION_RISK_BLOCKED.",
            "Broker-visible contract snapshot still matches or improves the reviewed contract.",
            "Manual preflight returns MANUAL_PREFLIGHT_READY.",
            "No market order; any broker action is manual and outside this MCP.",
            "If a buy sits pending for more than 60 seconds, re-review it before trusting it.",
        ],
        "action_links": {
            "morning_autopilot": f"/ops/morning-autopilot?tickers={','.join(universe)}&account_value={_float_or_zero(account_value) or 50.0}&max_candidates={max_candidates}",
            "live_review_cycle": f"/ops/live-review-cycle?tickers={','.join(universe)}&account_value={_float_or_zero(account_value) or 50.0}&max_candidates={max_candidates}&review_top_n={review_top_n}&max_contract_price={effective_contract_cap}",
            "review_harvest": f"/ops/review-harvest?tickers={','.join(universe)}&max_candidates={max_candidates}&review_top_n={review_top_n}&max_contract_price={effective_contract_cap}",
            "session_risk": f"/risk/session?account_value={_float_or_zero(account_value) or 50.0}&proposed_risk_dollars={proposed_risk}&max_open_positions=2&format=html",
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


def _run_market_open_observer(service_container, tickers: list[str] | None, max_candidates: int, cadence_minutes: int) -> dict:
    max_candidates = max(1, min(int(max_candidates or 25), 50))
    cadence_minutes = max(1, min(int(cadence_minutes or 5), 30))
    universe = _resolve_universe(service_container, tickers)
    scan = service_container.scanner.run_market_scan("scalp_review", universe, max_candidates)
    rows = list(scan.get("top_candidates") or []) + list(scan.get("pass_list") or [])
    valid_rows = [row for row in rows if row.get("data_status") == "valid"]
    candidate_rows = list(scan.get("top_candidates") or [])
    pass_rows = list(scan.get("pass_list") or [])
    evidence_batch = service_container.evidence_packets.build_packets_from_scan(scan, "market_open_observer")
    evidence_summary = evidence_batch.get("summary") or {}
    low_confidence_count = int((evidence_summary.get("data_confidence_counts") or {}).get("LOW") or 0)
    quote_problem_count = sum(1 for row in rows if any("quote" in str(reason).lower() for reason in (row.get("reasons") or [])))
    stale_count = sum(1 for row in rows if any("stale" in str(reason).lower() for reason in (row.get("reasons") or [])))

    if not rows:
        status = "OBSERVER_EMPTY"
        next_action = "No scan rows returned; verify provider, watchlist, and deployed build before reviewing candidates."
    elif not valid_rows:
        status = "OBSERVER_DATA_BLOCKED"
        next_action = "Do not run options review. Wait for clean quote/candle data or fix the data provider."
    elif low_confidence_count:
        status = "OBSERVER_LOW_CONFIDENCE"
        next_action = "Keep observing and saving evidence; do not tune rules from low-confidence packets."
    elif candidate_rows:
        status = "OBSERVER_STOCK_CANDIDATES"
        next_action = "After spreads stabilize, run live review cycle; only continue if stock setup and SMALL_ACCOUNT_SCALP_ACCEPTABLE both pass."
    else:
        status = "OBSERVER_NO_CANDIDATES"
        next_action = f"Keep observing every {cadence_minutes} minutes; no stock setup has cleared the gate yet."

    candidate_summaries = [_observer_row_summary(row) for row in candidate_rows[:max_candidates]]
    pass_summaries = [_observer_pass_summary(row) for row in pass_rows[: min(12, len(pass_rows))]]
    payload = {
        "status": status,
        "build_version": BUILD_VERSION,
        "mode": "market_open_observer",
        "generated_at": utc_now(),
        "universe": universe,
        "max_candidates": max_candidates,
        "cadence_minutes": cadence_minutes,
        "data_provider": scan.get("data_provider"),
        "data_status": scan.get("data_status"),
        "row_count": len(rows),
        "valid_row_count": len(valid_rows),
        "candidate_count": len(candidate_rows),
        "pass_count": len(pass_rows),
        "quote_problem_count": quote_problem_count,
        "stale_row_count": stale_count,
        "candidate_tickers": [row.get("ticker") for row in candidate_rows],
        "scan_summary": _scan_summary(scan),
        "evidence_batch_event_id": evidence_batch.get("id"),
        "evidence_packet_count": evidence_batch.get("packet_count"),
        "evidence_summary": evidence_summary,
        "candidate_observations": candidate_summaries,
        "pass_observations": pass_summaries,
        "delta_vs_previous_observer": _observer_delta(service_container, candidate_summaries),
        "next_action": next_action,
        "action_links": {
            "observer_refresh": f"/ops/market-open-observer?tickers={','.join(universe)}&max_candidates={max_candidates}&cadence_minutes={cadence_minutes}",
            "market_readiness": f"/ops/market-readiness?tickers={','.join(universe)}&max_candidates={max_candidates}",
            "live_review_cycle": f"/ops/live-review-cycle?tickers={','.join(universe)}&max_candidates={max_candidates}&review_top_n=8&max_contract_price={service_container.settings.scalp_max_contract_price}",
            "review_harvest": f"/ops/review-harvest?tickers={','.join(universe)}&max_candidates={max_candidates}&review_top_n=8&max_contract_price={service_container.settings.scalp_max_contract_price}",
            "journal_checkpoint": "/journal/checkpoint?limit=500&format=json",
        },
        "observer_rules": [
            "This observer records market evidence; it does not options-review, rank contracts, or create trade plans.",
            "Use it during the first 15-30 minutes to learn without chasing opening noise.",
            "Move to live review cycle only after data quality is acceptable and stock candidates exist.",
            "Export a journal checkpoint after meaningful observations so the evidence survives restarts.",
        ],
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "order_allowed": False,
        "broker_action": False,
    }
    return service_container.events.log("market_open_observer", payload)


def _run_observer_followup(service_container, limit_observations: int, max_items: int, include_passes: bool, classify: bool) -> dict:
    limit_observations = max(1, min(int(limit_observations or 3), 20))
    max_items = max(1, min(int(max_items or 20), 100))
    observations = service_container.events.recent("market_open_observer", limit_observations)
    if not observations:
        return service_container.events.log(
            "observer_followup",
            {
                "status": "NO_OBSERVER_TO_FOLLOW_UP",
                "reason": "No market_open_observer event has been logged yet.",
                "outcomes": [],
                "classifications": [],
                "review_only": True,
                "can_place_order_from_this_mcp": False,
                "can_cancel_order_from_this_mcp": False,
            },
        )

    followup_items = _observer_followup_items(observations, max_items, include_passes)
    outcomes: list[dict[str, Any]] = []
    classifications: list[dict[str, Any]] = []
    unavailable = 0
    for item in followup_items:
        outcome = service_container.review_outcomes.check_review_outcome(
            {
                "review_id": item["review_id"],
                "ticker": item.get("ticker"),
                "direction": item.get("direction") or "long",
                "entry_reference": item.get("entry_reference"),
                "review_timestamp": item.get("review_timestamp"),
            },
            {"15m": 3, "30m": 6, "60m": 12},
        )
        outcome["source_observer_event_id"] = item.get("source_observer_event_id")
        outcome["source_bucket"] = item.get("source_bucket")
        outcomes.append(outcome)
        if outcome.get("status") == "OUTCOME_UNAVAILABLE":
            unavailable += 1
        elif classify:
            classifications.append(service_container.learning.classify_review_outcome(item.get("snapshot") or item, outcome))

    learning_summary = service_container.learning.summarize_learning(classifications, max_items) if classifications else None
    proposals = service_container.learning.generate_rule_proposals(classifications, min_samples=3, limit=max_items) if classifications else None
    missed = [item for item in classifications if item.get("classification") in {"MISSED_MOVE", "BAD_CONTRACT_OR_TOO_STRICT"}]
    good_passes = [item for item in classifications if item.get("classification") in {"GOOD_PASS", "GOOD_BLOCK", "GOOD_CAUTION"}]
    if not outcomes:
        status = "OBSERVER_FOLLOWUP_EMPTY"
        next_action = "Run market-open observer first, then follow up once enough candles have elapsed."
    elif unavailable == len(outcomes):
        status = "OBSERVER_FOLLOWUP_OUTCOMES_UNAVAILABLE"
        next_action = "Market data could not grade the observer rows yet. Try again after more candles or provider recovery."
    elif missed:
        status = "OBSERVER_FOLLOWUP_LEARNING_NEEDED"
        next_action = "Review missed-move labels and rule proposals before changing any active gate."
    else:
        status = "OBSERVER_FOLLOWUP_COMPLETE"
        next_action = "Keep current gates; continue observing and checkpoint the journal after meaningful sessions."

    payload = {
        "status": status,
        "build_version": BUILD_VERSION,
        "mode": "observer_followup",
        "generated_at": utc_now(),
        "source_observation_count": len(observations),
        "items_checked": len(followup_items),
        "include_passes": bool(include_passes),
        "classify": bool(classify),
        "outcome_unavailable_count": unavailable,
        "missed_move_count": len(missed),
        "good_pass_count": len(good_passes),
        "outcomes": outcomes,
        "classifications": classifications,
        "learning_summary": learning_summary,
        "rule_proposals": proposals,
        "next_action": next_action,
        "action_links": {
            "market_open_observer": "/ops/market-open-observer",
            "learning_dashboard": "/learning/dashboard",
            "learning_proposals": "/learning/proposals",
            "journal_checkpoint": "/journal/checkpoint?limit=500&format=json",
        },
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "order_allowed": False,
        "broker_action": False,
        "notes": [
            "Observer follow-up grades previously observed candidates and pass rows.",
            "MISSED_MOVE labels are research signals only; rule changes still require backtesting.",
            "This tool cannot place, submit, simulate, modify, or cancel broker orders.",
        ],
    }
    return service_container.events.log("observer_followup", payload)


def _build_manual_trade_preflight_ticket(service_container, snapshot: dict[str, Any], account_value: float, max_contract_price: float | None, notes: str = "") -> dict:
    account_value = _float_or_zero(account_value) or 50.0
    effective_max_contract_price = max_contract_price
    if effective_max_contract_price is None:
        effective_max_contract_price = service_container.settings.scalp_max_contract_price
    option_validation = service_container.options.validate_broker_snapshot(snapshot, effective_max_contract_price)
    accepted_contracts = option_validation.get("accepted_contracts") or []
    selected = accepted_contracts[0] if accepted_contracts else None
    option_snapshot = option_validation.get("option_snapshot_v2") or {}
    liquidity_gate = option_validation.get("liquidity_gate_result") or {}
    mismatch_codes = option_validation.get("mismatch_codes") or []
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
    if mismatch_codes:
        blocking_reasons.extend([f"Broker snapshot mismatch: {code}" for code in mismatch_codes])
    if liquidity_gate.get("status") == "LIQUIDITY_GATE_BLOCK":
        blocking_reasons.append("Broker-visible liquidity/freshness gate blocked this snapshot.")
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
        "option_snapshot_v2": option_snapshot,
        "liquidity_gate_result": liquidity_gate,
        "mismatch_codes": mismatch_codes,
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
            "decision_record_v2": {
                "schema_version": "DecisionRecordV2",
                "decision_ts_utc": utc_now(),
                "rule_hash": _rules_hash(),
                "scan_receipt_id": snapshot.get("scan_id") or snapshot.get("scan_receipt_id"),
                "broker_snapshot_id": option_snapshot.get("source_receipt_time_utc"),
                "liquidity_gate_result": liquidity_gate.get("status"),
                "data_health_result": "SNAPSHOT_ACCEPTED" if not mismatch_codes else "SNAPSHOT_BLOCKED",
                "abstain_reason_codes": blocking_reasons,
                "evidence_refs": {
                    "option_snapshot_v2": option_snapshot,
                    "option_validation_event_id": option_validation.get("id"),
                },
            },
        },
        "checklist": [
            "Confirm the broker screen still matches this contract symbol.",
            "Confirm the quote timestamp is fresh and copied from the broker screen or captured now.",
            "Confirm bid/ask, volume, open interest, DTE, and max loss still pass.",
            "Confirm the contract is not adjusted/non-standard unless it has separate manual OCC review.",
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


def _build_manual_trade_desk(
    service_container,
    snapshot: dict[str, Any],
    account_value: float,
    max_contract_price: float | None,
    notes: str = "",
    max_open_positions: int = 2,
) -> dict:
    preflight = _build_manual_trade_preflight_ticket(service_container, snapshot, account_value, max_contract_price, notes)
    selected = preflight.get("selected_contract") or {}
    manual_ticket = preflight.get("manual_ticket") or {}
    contract_symbol = manual_ticket.get("contract_symbol") or selected.get("contract_symbol")
    reviewed_ask = _float_or_zero(manual_ticket.get("max_review_ask") or selected.get("ask"))
    proposed_risk = _float_or_zero(manual_ticket.get("max_loss_dollars") or selected.get("max_loss_dollars"))
    session_risk = _get_session_risk_guard(service_container, account_value, proposed_risk, max_open_positions)
    session_blocking_reasons = session_risk.get("blocking_reasons") or []
    session_warnings = session_risk.get("warnings") or []
    desk_blocking_reasons = list(preflight.get("blocking_reasons") or [])
    desk_warnings = list(preflight.get("warnings") or [])
    if session_risk.get("status") == "SESSION_RISK_BLOCKED":
        desk_blocking_reasons.extend([f"Session risk guard: {reason}" for reason in session_blocking_reasons])
    else:
        desk_warnings.extend([f"Session risk guard: {warning}" for warning in session_warnings])
    ready = preflight.get("status") == "MANUAL_PREFLIGHT_READY" and session_risk.get("status") != "SESSION_RISK_BLOCKED"
    underlying_reference = _float_or_zero(snapshot.get("underlying_price") or snapshot.get("price"))
    paper_payload = {
        "ticket": preflight,
        "fill_price": reviewed_ask,
        "quantity": manual_ticket.get("quantity") or 1,
        "underlying_price": underlying_reference if underlying_reference > 0 else None,
        "notes": notes or "manual trade desk paper log",
    } if ready else None
    payload = {
        "status": "MANUAL_TRADE_DESK_READY" if ready else "NO_TRADE_PLAN",
        "build_version": BUILD_VERSION,
        "ticker": preflight.get("ticker"),
        "direction": preflight.get("direction"),
        "contract_symbol": contract_symbol,
        "preflight": preflight,
        "session_risk_guard": session_risk,
        "blocking_reasons": desk_blocking_reasons,
        "warnings": desk_warnings,
        "paper_entry_request": {
            "endpoint": "/paper/options/entry",
            "payload": paper_payload,
        } if paper_payload else None,
        "checkpoint_request": {
            "endpoint": "/journal/checkpoint?limit=500&format=json",
            "when": "After any live review cycle, manual broker-side decision, paper entry, or paper close.",
        },
        "next_steps": [
            "Confirm the broker screen still shows this exact contract symbol.",
            "Confirm the broker snapshot timestamp is fresh; stale or missing timestamp means PASS.",
            "Confirm bid/ask, volume, open interest, DTE, strike, and max loss still match or improve this ticket.",
            "Confirm mismatch_codes is empty and liquidity_gate_result is LIQUIDITY_GATE_PASS.",
            "Confirm session risk guard remains clear before adding exposure.",
            "Use limit-only discipline; no market orders.",
            "If you manually act outside this MCP, log the paper/manual fill through /paper/options/entry for learning.",
            "If a buy remains pending after 60 seconds, re-review it before trusting it.",
            "Export /journal/checkpoint after the decision so the lesson survives restarts.",
        ] if ready else [
            "Do not inspect this as a trade candidate until the blocking reasons clear.",
            "Clear session-risk blockers before adding another manual idea.",
            "Rerun live review cycle or manual preflight only after broker-visible fields improve.",
            "Keep the result as NO_TRADE_PLAN.",
        ],
        "review_only": True,
        "paper_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "order_placed": False,
        "order_submitted": False,
        "broker_action": False,
        "notes": "Manual trade desk only. It prepares review, paper logging, and checkpoint steps; it cannot execute broker actions.",
    }
    return service_container.events.log("manual_trade_desk", payload)


def _log_manual_broker_action(service_container, action: dict[str, Any]) -> dict:
    ticker = str(action.get("ticker") or action.get("underlying") or "").upper()
    contract_symbol = str(action.get("contract_symbol") or action.get("symbol") or "")
    action_type = str(action.get("action_type") or action.get("manual_action") or "manual_note").lower()
    order_status = str(action.get("order_status") or action.get("status") or action_type).lower()
    side = str(action.get("side") or "buy").lower()
    direction = str(action.get("direction") or action.get("type") or "").lower()
    if direction in {"short", "put", "puts", "bearish"}:
        normalized_direction = "put"
    elif direction in {"long", "call", "calls", "bullish"}:
        normalized_direction = "call"
    else:
        normalized_direction = "put" if "P" in contract_symbol.upper()[-12:] else "call"
    quantity = max(1, int(_float_or_zero(action.get("quantity")) or 1))
    limit_price = _float_or_none_value(action.get("limit_price", action.get("price")))
    fill_price = _float_or_none_value(action.get("fill_price", action.get("execution_price")))
    reviewed_price = _float_or_none_value(action.get("reviewed_price", action.get("reviewed_ask")))
    pnl_dollars = _float_or_none_value(action.get("pnl_dollars", action.get("realized_pnl_dollars")))
    broker_snapshot_ts = _parse_manual_action_time(action.get("broker_snapshot_ts") or action.get("snapshot_ts"))
    execution_ts = _parse_manual_action_time(action.get("execution_ts") or action.get("filled_at") or action.get("submitted_at") or action.get("timestamp"))
    is_options_order = bool(action.get("is_options_order")) or bool(contract_symbol)
    is_real_cash = _boolish(action.get("is_real_cash", action.get("real_cash", True)))
    is_closing_action = _manual_action_is_close(action_type, order_status, side)
    submitted_dt = _parse_manual_action_time(action.get("submitted_at") or action.get("timestamp")) or datetime.now(UTC)
    submitted_at = submitted_dt.isoformat()
    pending_buy = _manual_action_is_pending_buy(action_type, order_status, side)
    recheck_after = submitted_dt + timedelta(seconds=service_container.settings.pending_buy_recheck_seconds) if pending_buy else None
    recheck_payload = {
        "ticker": ticker,
        "submitted_at": submitted_at,
        "limit_price": limit_price,
        "is_options_order": is_options_order,
        "direction": normalized_direction,
        "mode": action.get("mode") or "scalp_review",
    } if pending_buy else None
    execution_receipt = _manual_execution_receipt(action, submitted_at, broker_snapshot_ts, execution_ts, reviewed_price, fill_price, limit_price)
    payload = {
        "status": "MANUAL_ACTION_PENDING_RECHECK_REQUIRED" if pending_buy else "MANUAL_ACTION_LOGGED",
        "build_version": BUILD_VERSION,
        "ticker": ticker,
        "contract_symbol": contract_symbol,
        "action_type": action_type,
        "order_status": order_status,
        "side": side,
        "direction": normalized_direction,
        "quantity": quantity,
        "limit_price": limit_price,
        "fill_price": fill_price,
        "reviewed_price": reviewed_price,
        "pnl_dollars": pnl_dollars,
        "submitted_at": submitted_at,
        "broker_snapshot_ts": broker_snapshot_ts.isoformat() if broker_snapshot_ts else None,
        "execution_ts": execution_ts.isoformat() if execution_ts else None,
        "is_options_order": is_options_order,
        "is_real_cash": is_real_cash,
        "is_closing_action": is_closing_action,
        "real_cash_loss_countable": bool(is_real_cash and is_closing_action and pnl_dollars is not None and pnl_dollars < 0),
        "manual_execution_receipt_v1": execution_receipt,
        "execution_reconciliation": execution_receipt.get("reconciliation_status"),
        "mismatch_codes": execution_receipt.get("mismatch_codes"),
        "pending_buy": pending_buy,
        "pending_buy_recheck_seconds": service_container.settings.pending_buy_recheck_seconds,
        "recheck_after": recheck_after.isoformat() if recheck_after else None,
        "recheck_request": {
            "tool": "review_pending_buy_order",
            "endpoint": "/trade/pending-recheck",
            "payload": recheck_payload,
        } if recheck_payload else None,
        "journal_checkpoint_request": {
            "endpoint": "/journal/checkpoint?limit=500&format=json",
            "when": "After manual broker action logging, pending recheck, paper close, or learning classification.",
        },
        "next_steps": [
            "Wait until the recheck time before trusting the pending buy.",
            "Run the pending-buy recheck before leaving, canceling, or replacing the order manually.",
            "If the recheck returns RECONSIDER_PENDING_BUY, do not keep trusting the stale order.",
            "Export /journal/checkpoint after the decision so the evidence survives restarts.",
        ] if pending_buy else [
            "Keep this as a user-reported broker action record only.",
            "Use paper ledger or outcome tools if you want to study the result later.",
            "Export /journal/checkpoint after meaningful manual decisions.",
        ],
        "raw_action": action,
        "broker_action_was_user_reported": True,
        "mcp_broker_action": False,
        "order_placed_by_mcp": False,
        "order_submitted_by_mcp": False,
        "order_canceled_by_mcp": False,
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "notes": "Manual broker action journal only. This MCP records what the user reports; it cannot verify, place, submit, modify, or cancel broker orders.",
    }
    return service_container.events.log("manual_broker_action", payload)


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
    selected_snapshot = ticket.get("option_snapshot_v2") or (ticket.get("option_validation") or {}).get("option_snapshot_v2") or {}
    reviewed_ask = _float_or_none_value((ticket.get("manual_ticket") or {}).get("max_review_ask") or (ticket.get("selected_contract") or {}).get("ask"))
    price_drift = round(fill - reviewed_ask, 4) if reviewed_ask is not None else None
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
        "spread_at_decision": selected_snapshot.get("spread_pct_mid"),
        "spread_at_action": selected_snapshot.get("spread_pct_mid"),
        "reviewed_ask": reviewed_ask,
        "price_drift": price_drift,
        "decision_record_v2": (ticket.get("manual_ticket") or {}).get("decision_record_v2"),
        "option_snapshot_v2": selected_snapshot,
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
    signal_label = "SIGNAL_HELPED" if pnl > 0 else "SIGNAL_HURT" if pnl < 0 else "SIGNAL_FLAT"
    execution_label = _execution_outcome_label(entry, exit_value)
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
        "outcome_record_v2": {
            "schema_version": "OutcomeRecordV2",
            "signal_outcome_label": signal_label,
            "execution_outcome_label": execution_label,
            "actual_human_action": "paper_close",
            "actual_broker_result": "paper_only_no_broker_truth",
            "reconciliation_status": "PAPER_ONLY_UNRECONCILED",
            "price_drift": entry.get("price_drift"),
            "spread_at_decision": entry.get("spread_at_decision"),
            "spread_at_action": entry.get("spread_at_action"),
        },
        "signal_outcome_label": signal_label,
        "execution_outcome_label": execution_label,
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


def _watch_manual_option_position(
    service_container,
    entry_id: int | None,
    contract_symbol: str | None,
    current_bid: float | None,
    current_ask: float | None,
    current_mark: float | None,
    underlying_price: float | None,
    underlying_vwap: float | None,
    notes: str = "",
) -> dict:
    entry_event = _find_open_paper_entry(service_container, entry_id, contract_symbol)
    if not entry_event:
        return service_container.events.log(
            "manual_option_position_watch",
            {
                "status": "POSITION_WATCH_NO_OPEN_ENTRY",
                "reason": "No matching open paper/manual option entry was found.",
                "entry_id": entry_id,
                "contract_symbol": contract_symbol,
                "review_only": True,
                "can_place_order_from_this_mcp": False,
                "can_cancel_order_from_this_mcp": False,
                "broker_action": False,
            },
        )

    entry = entry_event.get("payload") or {}
    entry_price = _float_or_zero(entry.get("entry_price"))
    quantity = max(1, int(entry.get("quantity") or 1))
    bid = _float_or_zero(current_bid)
    ask = _float_or_zero(current_ask)
    mark = _float_or_zero(current_mark)
    if mark <= 0 and bid > 0 and ask > 0:
        mark = round((bid + ask) / 2, 4)
    if mark <= 0:
        return service_container.events.log(
            "manual_option_position_watch",
            {
                "status": "POSITION_WATCH_NEEDS_LIVE_QUOTE",
                "reason": "Provide current_mark or current bid/ask from the broker screen.",
                "entry_event_id": entry_event.get("id"),
                "ticker": entry.get("ticker"),
                "contract_symbol": entry.get("contract_symbol"),
                "entry_price": entry_price,
                "review_only": True,
                "can_place_order_from_this_mcp": False,
                "can_cancel_order_from_this_mcp": False,
                "broker_action": False,
            },
        )

    return_pct = round((mark - entry_price) / entry_price, 5) if entry_price > 0 else None
    pnl_dollars = round((mark - entry_price) * 100 * quantity, 2) if entry_price > 0 else None
    spread_pct = round((ask - bid) / ((ask + bid) / 2), 4) if bid > 0 and ask > 0 and ask >= bid else None
    direction = str(entry.get("direction") or "").lower()
    underlying = _float_or_zero(underlying_price)
    vwap = _float_or_zero(underlying_vwap)
    warnings: list[str] = []
    exit_reasons: list[str] = []

    if spread_pct is not None and spread_pct > 0.25:
        warnings.append("Option spread is very wide; do not use market orders and avoid chasing exits.")
        exit_reasons.append("spread_too_wide")
    elif spread_pct is not None and spread_pct > 0.15:
        warnings.append("Option spread is wider than preferred; limit-only discipline required.")

    adverse_vwap = False
    if underlying > 0 and vwap > 0:
        if direction in {"put", "puts", "short"} and underlying >= vwap:
            adverse_vwap = True
            warnings.append("Underlying is at/above VWAP against the put thesis.")
            exit_reasons.append("underlying_reclaimed_vwap")
        elif direction in {"call", "calls", "long"} and underlying <= vwap:
            adverse_vwap = True
            warnings.append("Underlying is at/below VWAP against the call thesis.")
            exit_reasons.append("underlying_lost_vwap")

    if return_pct is not None and return_pct <= -0.5:
        status = "POSITION_STOP_REVIEW"
        next_action = "Loss is severe for a small-account option; review manual close immediately."
        exit_reasons.append("hard_loss_threshold")
    elif return_pct is not None and return_pct <= -0.35:
        status = "POSITION_STOP_REVIEW"
        next_action = "Loss threshold hit; review manual close or reduce exposure."
        exit_reasons.append("loss_threshold")
    elif adverse_vwap and (return_pct is None or return_pct <= 0.1):
        status = "POSITION_STOP_REVIEW"
        next_action = "Underlying invalidated the thesis; review manual close instead of hoping."
    elif return_pct is not None and return_pct >= 0.5:
        status = "POSITION_PROFIT_REVIEW"
        next_action = "Large option gain; consider manual profit-taking or tight stop discipline."
        exit_reasons.append("profit_target")
    elif return_pct is not None and return_pct >= 0.25:
        status = "POSITION_PROFIT_WATCH"
        next_action = "Position is working; consider protecting gains and avoid letting a winner turn red."
        exit_reasons.append("profit_watch")
    else:
        status = "POSITION_HOLD_REVIEW"
        next_action = "No hard exit trigger; keep watching thesis, spread, and option mark."

    suggested_exit_reason = exit_reasons[0] if exit_reasons else "manual_review"
    payload = {
        "status": status,
        "build_version": BUILD_VERSION,
        "entry_event_id": entry_event.get("id"),
        "entry_timestamp": entry.get("entry_timestamp"),
        "ticker": entry.get("ticker"),
        "direction": direction,
        "contract_symbol": entry.get("contract_symbol"),
        "entry_price": entry_price,
        "quantity": quantity,
        "current_bid": bid if bid > 0 else None,
        "current_ask": ask if ask > 0 else None,
        "current_mark": mark,
        "underlying_price": underlying if underlying > 0 else None,
        "underlying_vwap": vwap if vwap > 0 else None,
        "return_pct": return_pct,
        "pnl_dollars": pnl_dollars,
        "spread_pct": spread_pct,
        "warnings": warnings,
        "next_action": next_action,
        "close_request": {
            "endpoint": "/paper/options/close",
            "entry_id": entry_event.get("id"),
            "contract_symbol": entry.get("contract_symbol"),
            "exit_price": mark,
            "exit_reason": suggested_exit_reason,
            "notes": "Prepared by position watch; user must decide and act manually outside this MCP.",
        },
        "management_rules": [
            "Review stop if option mark is down 35% or more from entry.",
            "Review hard stop immediately if option mark is down 50% or more.",
            "Review profit protection once option mark is up 25%; consider taking/locking gains above 50%.",
            "For puts, VWAP reclaim by the underlying weakens the thesis; for calls, VWAP loss weakens it.",
            "Use limit-only discipline; no market orders.",
        ],
        "notes": notes,
        "paper_only": True,
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "order_placed": False,
        "order_submitted": False,
        "broker_action": False,
    }
    return service_container.events.log("manual_option_position_watch", payload)


def _get_session_risk_guard(service_container, account_value: float = 50.0, proposed_risk_dollars: float | None = None, max_open_positions: int = 2) -> dict:
    account_value = _float_or_zero(account_value) or 50.0
    max_open_positions = max(1, min(int(max_open_positions or 2), 5))
    proposed_risk = _float_or_zero(proposed_risk_dollars)
    trading_day_timezone = "America/Chicago"
    today = datetime.now(UTC).astimezone(ZoneInfo(trading_day_timezone)).date().isoformat()
    max_daily_real_cash_closed_losses = max(1, int(getattr(service_container.settings, "max_daily_real_cash_closed_losses", 3) or 3))
    entries = [
        event
        for event in service_container.events.recent("manual_option_paper_entry", 500)
        if (event.get("payload") or {}).get("status") in {"PAPER_OPTION_ENTRY_OPEN", "PAPER_ENTRY_LOGGED_FROM_UNREADY_TICKET"}
    ]
    closes = [
        event
        for event in service_container.events.recent("manual_option_paper_close", 500)
        if (event.get("payload") or {}).get("status") == "PAPER_OPTION_CLOSED"
    ]
    cash_actions = service_container.events.recent("manual_broker_action", 500)
    real_cash_closes = [event for event in cash_actions if _manual_broker_event_is_real_cash_close(event)]
    todays_real_cash_closes = [event for event in real_cash_closes if _event_local_date(event, trading_day_timezone) == today]
    real_cash_entries = [event for event in cash_actions if _manual_broker_event_is_real_cash_entry(event)]
    closed_entry_ids = {(event.get("payload") or {}).get("entry_event_id") for event in closes}
    open_entries = [event for event in entries if event.get("id") not in closed_entry_ids]
    todays_closes = [event for event in closes if _event_local_date(event, trading_day_timezone) == today]
    daily_pnls = [_float_or_zero((event.get("payload") or {}).get("pnl_dollars")) for event in todays_closes]
    daily_closed_pnl = round(sum(daily_pnls), 2)
    daily_loss_count = sum(1 for pnl in daily_pnls if pnl < 0)
    daily_win_count = sum(1 for pnl in daily_pnls if pnl > 0)
    daily_flat_count = sum(1 for pnl in daily_pnls if pnl == 0)
    real_cash_daily_pnls = [_float_or_zero((event.get("payload") or {}).get("pnl_dollars")) for event in todays_real_cash_closes]
    real_cash_daily_closed_pnl = round(sum(real_cash_daily_pnls), 2)
    real_cash_daily_loss_count = sum(1 for pnl in real_cash_daily_pnls if pnl < 0)
    real_cash_daily_win_count = sum(1 for pnl in real_cash_daily_pnls if pnl > 0)
    real_cash_daily_flat_count = sum(1 for pnl in real_cash_daily_pnls if pnl == 0)
    real_cash_open_position_count = max(0, len(real_cash_entries) - len(real_cash_closes))
    open_risk = round(sum(_float_or_zero((event.get("payload") or {}).get("entry_debit_dollars")) for event in open_entries), 2)
    closed_pnl = round(sum(_float_or_zero((event.get("payload") or {}).get("pnl_dollars")) for event in closes), 2)
    per_trade_cap = round(account_value * service_container.settings.max_trade_risk_pct, 2)
    warn_drawdown = round(account_value * service_container.settings.warn_daily_drawdown_pct, 2)
    soft_stop = round(account_value * service_container.settings.soft_stop_daily_drawdown_pct, 2)
    hard_lockout = round(account_value * service_container.settings.hard_lockout_daily_drawdown_pct, 2)
    total_open_cap = round(account_value * service_container.settings.hard_lockout_daily_drawdown_pct, 2)
    projected_open_risk = round(open_risk + proposed_risk, 2)
    warnings: list[str] = []
    blocking_reasons: list[str] = []

    if proposed_risk > 0 and proposed_risk > per_trade_cap:
        blocking_reasons.append("Proposed risk exceeds per-trade journal risk cap.")
    if real_cash_open_position_count >= max_open_positions:
        blocking_reasons.append("Max user-reported real-cash option positions already reached.")
    if real_cash_daily_loss_count >= max_daily_real_cash_closed_losses:
        blocking_reasons.append(f"Real-cash daily closed-loss lockout reached ({real_cash_daily_loss_count}/{max_daily_real_cash_closed_losses} losses).")
    if real_cash_daily_closed_pnl <= -hard_lockout:
        blocking_reasons.append("Real-cash daily closed P/L reached hard lockout reference.")
    elif real_cash_daily_closed_pnl <= -soft_stop:
        warnings.append("Real-cash daily closed P/L is beyond soft-stop reference.")
    elif real_cash_daily_closed_pnl <= -warn_drawdown:
        warnings.append("Real-cash daily closed P/L is beyond warning reference.")

    if blocking_reasons:
        status = "SESSION_RISK_BLOCKED"
        next_action = "Do not add another manual option idea; reduce/close risk or wait."
    elif warnings:
        status = "SESSION_RISK_CAUTION"
        next_action = "Proceed only with extra discipline; prefer managing existing exposure over adding risk."
    else:
        status = "SESSION_RISK_CLEAR"
        next_action = "Risk journal is clear for review; still require live review cycle and manual trade desk."

    open_summaries = [
        {
            "entry_event_id": event.get("id"),
            "timestamp": event.get("timestamp"),
            "ticker": (event.get("payload") or {}).get("ticker"),
            "contract_symbol": (event.get("payload") or {}).get("contract_symbol"),
            "direction": (event.get("payload") or {}).get("direction"),
            "entry_price": (event.get("payload") or {}).get("entry_price"),
            "quantity": (event.get("payload") or {}).get("quantity"),
            "entry_debit_dollars": (event.get("payload") or {}).get("entry_debit_dollars"),
        }
        for event in open_entries[:20]
    ]
    payload = {
        "status": status,
        "build_version": BUILD_VERSION,
        "mode": "session_risk_guard",
        "generated_at": utc_now(),
        "account_value_reference": account_value,
        "proposed_risk_dollars": proposed_risk if proposed_risk > 0 else None,
        "per_trade_cap_dollars": per_trade_cap,
        "total_open_risk_cap_dollars": total_open_cap,
        "warning_drawdown_dollars": warn_drawdown,
        "soft_stop_dollars": soft_stop,
        "hard_lockout_dollars": hard_lockout,
        "trading_day": today,
        "trading_day_timezone": trading_day_timezone,
        "open_position_count": len(open_entries),
        "paper_open_position_count": len(open_entries),
        "real_cash_open_position_count": real_cash_open_position_count,
        "max_open_positions": max_open_positions,
        "open_risk_dollars": open_risk,
        "paper_open_risk_dollars": open_risk,
        "projected_open_risk_dollars": projected_open_risk,
        "closed_pnl_dollars": closed_pnl,
        "closed_trade_count": len(closes),
        "paper_daily_closed_pnl_dollars": daily_closed_pnl,
        "paper_daily_closed_trade_count": len(todays_closes),
        "paper_daily_loss_count": daily_loss_count,
        "paper_daily_win_count": daily_win_count,
        "paper_daily_flat_count": daily_flat_count,
        "daily_closed_pnl_dollars": daily_closed_pnl,
        "daily_closed_trade_count": len(todays_closes),
        "daily_loss_count": daily_loss_count,
        "daily_win_count": daily_win_count,
        "daily_flat_count": daily_flat_count,
        "daily_loss_lockout_count": None,
        "daily_loss_lockout_triggered": False,
        "real_cash_daily_closed_pnl_dollars": real_cash_daily_closed_pnl,
        "real_cash_daily_closed_trade_count": len(todays_real_cash_closes),
        "real_cash_daily_loss_count": real_cash_daily_loss_count,
        "real_cash_daily_win_count": real_cash_daily_win_count,
        "real_cash_daily_flat_count": real_cash_daily_flat_count,
        "real_cash_daily_loss_lockout_count": max_daily_real_cash_closed_losses,
        "real_cash_daily_loss_lockout_triggered": real_cash_daily_loss_count >= max_daily_real_cash_closed_losses,
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
        "open_entries": open_summaries,
        "next_action": next_action,
        "action_links": {
            "day_alerts": "/ops/day-alerts?limit=50&format=html",
            "paper_ledger": "/paper/options/summary?format=html",
            "position_watch": "/paper/options/watch",
            "manual_trade_desk": "/trade/manual-desk",
            "journal_checkpoint": "/journal/checkpoint?limit=500&format=json",
        },
        "rules": [
            "This guard uses MCP journal evidence only; it does not know actual broker balances or positions.",
            "Paper/research scanning, paper entries, and paper closes are uncapped for learning.",
            f"Block real-cash/autonomous escalation after {max_daily_real_cash_closed_losses} user-reported real-cash closed losses in the current trading day.",
            "Do not add real-cash exposure if pending-buy recheck, real-cash daily loss lockout, real-cash hard lockout, or max user-reported real-cash positions is triggered.",
            "Live review cycle and manual trade desk are still required before any broker-side manual action.",
            "No market orders.",
        ],
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "broker_action": False,
    }
    return service_container.events.log("session_risk_guard", payload)


def _get_failure_mode_audit(service_container) -> dict:
    tool_names = [getattr(tool, "name", str(tool)) for tool in service_container.mcp._tool_manager._tools.values()] if hasattr(service_container, "mcp") else []
    controls = [
        {
            "area": "Broker execution containment",
            "status": "HARD_BLOCKED",
            "covered_by": ["review_only", "place_orders=false", "can_place_order_from_this_mcp=false", "can_cancel_order_from_this_mcp=false"],
            "evidence": "This service does not store broker credentials and exposes no broker execution path.",
            "remaining_gap": "Manual broker actions still depend on the operator following the desk ticket.",
            "next_hardening": "Keep all broker actions outside this MCP until paper/manual logs prove repeatability.",
        },
        {
            "area": "Market data freshness and corruption",
            "status": "PARTIAL_CONTROL",
            "covered_by": ["quote/candle freshness gates", "stale quote rejection", "market_readiness_check", "evidence_packet provider lineage"],
            "evidence": "Scan rows expose provider lineage, freshness flags, data confidence, and quote/candle rejection reasons.",
            "remaining_gap": "No paid OPRA feed or independent real-time options quote source is connected.",
            "next_hardening": "Add cross-source quote divergence checks and explicit broker-visible snapshot comparison before any manual action.",
        },
        {
            "area": "Backtest leakage and overfitting",
            "status": "WATCHLIST_CONTROL",
            "covered_by": ["backtest endpoint", "learning proposals are manual only", "no auto-applied rule changes"],
            "evidence": "Rule proposals are research memory only and must be manually reviewed/backtested before gate changes.",
            "remaining_gap": "No formal purged walk-forward or deflated-Sharpe/PBO report yet.",
            "next_hardening": "Add a research-trial ledger and walk-forward validation report before loosening live gates.",
        },
        {
            "area": "Train-serve skew",
            "status": "PARTIAL_CONTROL",
            "covered_by": ["scan_schema", "evidence_scorecard", "setup_fingerprint", "health/full schema versions"],
            "evidence": "Debug schema exposes expected candidate fields and health reports schema versions.",
            "remaining_gap": "Feature definitions are still service-code based rather than one declarative registry used by both research and live scoring.",
            "next_hardening": "Promote scoring fields into a versioned feature contract and fail closed when critical fields are missing.",
        },
        {
            "area": "Slippage, spread, and liquidity illusion",
            "status": "ACTIVE_CONTROL",
            "covered_by": ["friction_adjusted_review", "small_account_review", "manual snapshot form", "limit-only rule"],
            "evidence": "Options review scores spread, volume, open interest, max loss, and small-account suitability.",
            "remaining_gap": "Actual fill quality is not automatically reconciled against broker fills.",
            "next_hardening": "Log intended limit, broker-visible bid/ask, actual fill, and outcome to build a slippage ledger.",
        },
        {
            "area": "Order-state divergence and stale pending buys",
            "status": "MANUAL_CONTROL",
            "covered_by": ["review_pending_buy_order", "pending_buy_recheck_seconds=60", "manual broker action journal"],
            "evidence": "Pending buys older than 60 seconds require reconsideration before trust.",
            "remaining_gap": "The MCP cannot directly reconcile live options orders from a brokerage account.",
            "next_hardening": "Require operator-entered pending-order snapshots for any visible pending buy older than 60 seconds.",
        },
        {
            "area": "Session risk and concentration",
            "status": "ACTIVE_CONTROL",
            "covered_by": ["get_session_risk_guard", "paper option ledger", "max open positions", "per-trade risk cap"],
            "evidence": "Session guard blocks additional ideas when local open paper/manual risk breaches thresholds.",
            "remaining_gap": "Broker account balance and open positions are not independently verified inside this MCP.",
            "next_hardening": "Add a manual broker-balance confirmation field to the morning launch checklist.",
        },
        {
            "area": "Learning drift and false confidence",
            "status": "ACTIVE_CONTROL",
            "covered_by": ["check_review_outcome", "classify_review_outcome", "summarize_learning", "generate_learning_rule_proposals"],
            "evidence": "Outcomes and false positives are logged, summarized, and kept separate from live gate changes.",
            "remaining_gap": "No formal calibration curve by confidence bucket yet.",
            "next_hardening": "Track win/loss and MFE/MAE by confidence band, setup fingerprint, ticker, DTE, and spread bucket.",
        },
        {
            "area": "Observability and replay",
            "status": "ACTIVE_CONTROL",
            "covered_by": ["journal checkpoint", "release manifest", "health/full", "evidence packets", "paper ledger"],
            "evidence": "Build, tool count, schema versions, safety, evidence, and local journal state can be replayed.",
            "remaining_gap": "No immutable external log store; Render local storage may not be durable across rebuilds.",
            "next_hardening": "Export checkpoints after each session and before/after any package upload.",
        },
    ]
    blocked_until = [
        "Do not enable broker execution from this MCP.",
        "Do not loosen score or option gates from a single trade or a single day.",
        "Do not trust stock setup alone without small-account options validation.",
        "Do not trust options-chain quality alone without a valid directional stock setup.",
        "Do not treat a stale pending buy as valid after 60 seconds without recheck.",
        "Do not use market orders.",
    ]
    highest_priority_next = [
        "Add broker-visible snapshot/fill/slippage comparison to every manual action journal entry.",
        "Add confidence-bucket outcome reporting to learning dashboard.",
        "Add a walk-forward validation report before changing tomorrow's live thresholds.",
        "Add morning broker-balance/open-position confirmation to launch checklist.",
    ]
    payload = {
        "status": "FAILURE_MODE_AUDIT_READY",
        "build_version": BUILD_VERSION,
        "generated_at": utc_now(),
        "source": "agentic_trading_failure_modes_research",
        "tool_count_observed": len(tool_names),
        "control_summary": {
            "hard_blocked": sum(1 for item in controls if item["status"] == "HARD_BLOCKED"),
            "active_control": sum(1 for item in controls if item["status"] == "ACTIVE_CONTROL"),
            "partial_control": sum(1 for item in controls if item["status"] == "PARTIAL_CONTROL"),
            "manual_control": sum(1 for item in controls if item["status"] == "MANUAL_CONTROL"),
            "watchlist_control": sum(1 for item in controls if item["status"] == "WATCHLIST_CONTROL"),
        },
        "controls": controls,
        "blocked_until": blocked_until,
        "highest_priority_next": highest_priority_next,
        "operator_read": "The system is safest where it is bounded and replayable. Accuracy improves by logging every review, failed setup, manual broker snapshot, fill, and outcome before changing rules.",
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "order_allowed": False,
        "notes": [
            "This audit does not run a scan and does not create a trade plan.",
            "It maps known trading-bot failure modes to current controls and gaps.",
            "Rule changes from this audit still require tests, backtests, and manual approval.",
        ],
    }
    return service_container.events.log("failure_mode_audit", payload)


def _run_paper_exploration(
    service_container,
    tickers: list[str] | None,
    max_candidates: int,
    max_trials: int,
    max_contract_price: float | None,
    include_passes: bool,
    exploration_level: str,
) -> dict:
    max_candidates = max(1, min(int(max_candidates or 50), 75))
    max_trials = max(1, min(int(max_trials or 20), 40))
    level = str(exploration_level or "aggressive").strip().lower()
    if level not in {"balanced", "aggressive", "chaos"}:
        level = "aggressive"
    universe = _resolve_universe(service_container, tickers)
    effective_contract_cap = max_contract_price
    if effective_contract_cap is None:
        effective_contract_cap = service_container.settings.scalp_max_contract_price
    if level == "chaos":
        effective_contract_cap = max(effective_contract_cap or 1.0, 2.5)
    elif level == "aggressive":
        effective_contract_cap = max(effective_contract_cap or 1.0, 1.5)

    scan = service_container.scanner.run_market_scan("scalp_review", universe, max_candidates)
    candidate_rows = list(scan.get("top_candidates") or [])
    pass_rows = list(scan.get("pass_list") or []) if include_passes else []
    row_pool = candidate_rows + pass_rows
    row_pool.sort(key=lambda row: _float_or_zero(row.get("score")), reverse=True)

    trials: list[dict[str, Any]] = []
    opened_entries = 0
    blocked_no_price = 0
    blocked_no_direction = 0
    review_count = 0
    for row in row_pool[:max_trials]:
        ticker = str(row.get("ticker") or "").upper()
        direction = _paper_exploration_direction(row)
        if not ticker or direction not in {"long", "short"}:
            blocked_no_direction += 1
            trials.append(_paper_exploration_trial_record(row, None, None, "NO_DIRECTION_FOR_PAPER_TRIAL", None, None))
            continue

        option_direction = "call" if direction == "long" else "put"
        review = _review_candidate_for_options(service_container, ticker, option_direction, "scalp_review", effective_contract_cap)
        review_count += 1
        contract, contract_source = _paper_exploration_contract_from_review(review)
        fill_price, price_source = _paper_exploration_fill_price(contract)
        if not contract or fill_price <= 0:
            blocked_no_price += 1
            trials.append(_paper_exploration_trial_record(row, review, contract, "NO_PRICE_FOR_PAPER_ENTRY", contract_source, price_source))
            continue

        paper_quality = _paper_exploration_quality(row, review, contract, level)
        ticket = {
            "status": "PAPER_EXPLORATION_TRIAL",
            "ticker": ticker,
            "direction": option_direction,
            "selected_contract": contract,
            "stock_setup": row,
            "options_review": review,
            "paper_exploration": {
                "schema_version": "paper_exploration_v1",
                "level": level,
                "paper_quality": paper_quality,
                "contract_source": contract_source,
                "price_source": price_source,
                "cash_gate_unchanged": True,
                "cash_eligible": False,
                "why_allowed_in_paper": _paper_exploration_reason(row, review, contract, paper_quality),
            },
        }
        entry = _log_manual_option_paper_entry(
            service_container,
            ticket,
            fill_price,
            1,
            _paper_exploration_underlying_reference(row),
            f"auto paper exploration: {paper_quality}; {price_source}",
        )
        opened_entries += 1
        trial = _paper_exploration_trial_record(row, review, contract, "PAPER_EXPLORATION_ENTRY_OPENED", contract_source, price_source)
        trial["entry_event_id"] = entry.get("id")
        trial["entry_price"] = fill_price
        trial["paper_quality"] = paper_quality
        trials.append(trial)

    quality_counts = Counter(str(item.get("paper_quality") or item.get("status") or "unknown") for item in trials)
    payload = {
        "status": "PAPER_EXPLORATION_TRIALS_OPENED" if opened_entries else "PAPER_EXPLORATION_NO_ENTRIES",
        "build_version": BUILD_VERSION,
        "schema_version": "paper_exploration_v1",
        "mode": "paper_exploration",
        "generated_at": utc_now(),
        "exploration_level": level,
        "universe": universe,
        "max_candidates": max_candidates,
        "max_trials": max_trials,
        "max_contract_price_used": effective_contract_cap,
        "include_passes": bool(include_passes),
        "scan_summary": _scan_summary(scan),
        "candidate_row_count": len(candidate_rows),
        "pass_row_count": len(pass_rows),
        "review_count": review_count,
        "opened_entry_count": opened_entries,
        "blocked_no_direction_count": blocked_no_direction,
        "blocked_no_price_count": blocked_no_price,
        "quality_counts": dict(quality_counts),
        "trials": trials,
        "followup_link": "/paper/exploration/followup?limit_runs=5&max_items=80&classify=true&format=html",
        "summary_link": "/paper/exploration/summary?format=html",
        "cash_gate_status": {
            "cash_gates_changed": False,
            "real_money_allowed_from_this_output": False,
            "paper_bad_trades_allowed": True,
            "purpose": "Increase labeled samples, including failures, without weakening live/cash gates.",
        },
        "review_only": True,
        "paper_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "order_allowed": False,
        "broker_action": False,
        "notes": [
            "Paper exploration intentionally opens low-quality research trials to learn faster.",
            "Every trial is tagged; do not mix paper-exploration losses with cash-strategy failures.",
            "This tool does not contact a broker and cannot place, submit, simulate, modify, or cancel orders.",
        ],
    }
    return service_container.events.log("paper_exploration_run", payload)


def _run_paper_exploration_followup(service_container, limit_runs: int, max_items: int, classify: bool) -> dict:
    limit_runs = max(1, min(int(limit_runs or 5), 20))
    max_items = max(1, min(int(max_items or 80), 200))
    runs = service_container.events.recent("paper_exploration_run", limit_runs)
    followup_items: list[dict[str, Any]] = []
    for event in runs:
        payload = event.get("payload") or {}
        for trial in payload.get("trials") or []:
            if trial.get("status") != "PAPER_EXPLORATION_ENTRY_OPENED":
                continue
            item = dict(trial)
            item["source_run_event_id"] = event.get("id")
            item["source_run_timestamp"] = event.get("timestamp")
            followup_items.append(item)
            if len(followup_items) >= max_items:
                break
        if len(followup_items) >= max_items:
            break

    outcomes: list[dict[str, Any]] = []
    classifications: list[dict[str, Any]] = []
    unavailable = 0
    for item in followup_items:
        entry_reference = _paper_exploration_entry_reference_from_item(service_container, item)
        outcome = service_container.review_outcomes.check_review_outcome(
            {
                "review_id": f"paper-exploration-{item.get('entry_event_id') or item.get('ticker')}",
                "ticker": item.get("ticker"),
                "direction": item.get("stock_direction") or "long",
                "entry_reference": entry_reference,
                "review_timestamp": item.get("source_run_timestamp"),
            },
            {"15m": 3, "30m": 6, "60m": 12},
        )
        outcome["entry_event_id"] = item.get("entry_event_id")
        outcome["paper_quality"] = item.get("paper_quality")
        outcome["ticker"] = item.get("ticker")
        outcomes.append(outcome)
        if outcome.get("status") == "OUTCOME_UNAVAILABLE":
            unavailable += 1
        elif classify:
            classifications.append(service_container.learning.classify_review_outcome(item, outcome))

    helped = [
        item
        for item in outcomes
        if _float_or_zero(item.get("directional_return") or item.get("current_return_pct")) > 0
    ]
    hurt = [
        item
        for item in outcomes
        if _float_or_zero(item.get("directional_return") or item.get("current_return_pct")) < 0
    ]
    learning_summary = service_container.learning.summarize_learning(classifications, max_items) if classifications else None
    status = "PAPER_EXPLORATION_FOLLOWUP_READY" if outcomes and unavailable < len(outcomes) else "PAPER_EXPLORATION_FOLLOWUP_WAITING"
    payload = {
        "status": status,
        "build_version": BUILD_VERSION,
        "schema_version": "paper_exploration_followup_v1",
        "mode": "paper_exploration_followup",
        "generated_at": utc_now(),
        "source_run_count": len(runs),
        "items_checked": len(followup_items),
        "outcome_unavailable_count": unavailable,
        "helped_count": len(helped),
        "hurt_count": len(hurt),
        "outcomes": outcomes,
        "classifications": classifications,
        "learning_summary": learning_summary,
        "next_action": "Compare exploratory losses to exploratory winners before changing any real-money gate.",
        "review_only": True,
        "paper_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "order_allowed": False,
        "broker_action": False,
        "notes": [
            "Follow-up grades underlying movement from paper-exploration entries.",
            "Option P/L remains approximate unless the operator supplies broker-visible option marks.",
            "Use this to learn what not to trade as aggressively as what to trade.",
        ],
    }
    return service_container.events.log("paper_exploration_followup", payload)


def _summarize_paper_exploration(service_container, limit: int = 100) -> dict:
    limit = max(1, min(int(limit or 100), 500))
    runs = service_container.events.recent("paper_exploration_run", limit)
    followups = service_container.events.recent("paper_exploration_followup", limit)
    trials: list[dict[str, Any]] = []
    for event in runs:
        for trial in (event.get("payload") or {}).get("trials") or []:
            trials.append(trial)
    opened = [item for item in trials if item.get("status") == "PAPER_EXPLORATION_ENTRY_OPENED"]
    quality_counts = Counter(str(item.get("paper_quality") or item.get("status") or "unknown") for item in trials)
    ticker_counts = Counter(str(item.get("ticker") or "UNKNOWN") for item in opened)
    followup_payloads = [event.get("payload") or {} for event in followups]
    payload = {
        "status": "PAPER_EXPLORATION_SUMMARY_READY",
        "build_version": BUILD_VERSION,
        "schema_version": "paper_exploration_summary_v1",
        "run_count": len(runs),
        "trial_count": len(trials),
        "opened_entry_count": len(opened),
        "quality_counts": dict(quality_counts),
        "top_tickers": dict(ticker_counts.most_common(12)),
        "latest_followup": followup_payloads[0] if followup_payloads else None,
        "links": {
            "run_aggressive": "/paper/exploration/run?max_candidates=50&max_trials=20&exploration_level=aggressive&include_passes=true&format=html",
            "run_chaos": "/paper/exploration/run?max_candidates=75&max_trials=35&exploration_level=chaos&include_passes=true&format=html",
            "followup": "/paper/exploration/followup?limit_runs=5&max_items=80&classify=true&format=html",
            "manual_paper_ledger": "/paper/options/summary?format=html",
            "checkpoint": "/journal/checkpoint?limit=500&format=json",
        },
        "cash_gate_status": {
            "cash_gates_changed": False,
            "real_money_allowed_from_this_output": False,
            "paper_bad_trades_allowed": True,
        },
        "review_only": True,
        "paper_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "order_allowed": False,
        "broker_action": False,
        "notes": "Paper exploration is intentionally noisy. Treat it as data mining, not a live strategy score.",
    }
    return service_container.events.log("paper_exploration_summary", payload)


def _paper_exploration_direction(row: dict[str, Any]) -> str:
    direction = str(row.get("direction") or "").lower()
    if direction in {"long", "short"}:
        return direction
    signals = row.get("key_signals") or {}
    if signals.get("above_vwap"):
        return "long"
    if signals.get("below_vwap"):
        return "short"
    trend = _float_or_none_value(signals.get("trend_pct") or signals.get("recent_trend_pct") or signals.get("change_vs_previous_close"))
    if trend is not None and trend > 0:
        return "long"
    if trend is not None and trend < 0:
        return "short"
    return "none"


def _paper_exploration_contract_from_review(review: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str | None]:
    if not review:
        return None, None
    small = review.get("small_account_review") or {}
    selected = small.get("selected_contract")
    if selected:
        return selected, "small_account_selected_contract"
    gate = review.get("options_chain_validation") or {}
    accepted = gate.get("accepted_contracts") or []
    if accepted:
        return accepted[0], "accepted_contract_cash_blocked_by_friction"
    rejected = gate.get("best_rejected_contracts") or gate.get("rejected_contracts") or []
    if rejected:
        return rejected[0], "best_rejected_contract_paper_only"
    return None, None


def _paper_exploration_fill_price(contract: dict[str, Any] | None) -> tuple[float, str | None]:
    if not contract:
        return 0.0, None
    for key, source in (("ask", "ask"), ("midpoint", "midpoint"), ("last_price", "last_price"), ("bid", "bid")):
        value = _float_or_zero(contract.get(key))
        if value > 0:
            return value, source
    return 0.0, "no_positive_price"


def _paper_exploration_quality(row: dict[str, Any], review: dict[str, Any] | None, contract: dict[str, Any], level: str) -> str:
    if review and review.get("status") == "REVIEW_ONLY_OPTIONS_READY":
        return "would_have_passed_review"
    small = (review or {}).get("small_account_review") or {}
    if small.get("status") == "NO_TRADE_PLAN":
        return "cash_blocked_by_small_account_friction"
    if (review or {}).get("status") == "NO_TRADE_PLAN":
        return "cash_blocked_by_stock_or_options_gate"
    if (row.get("quality_gates") or {}).get("stock_setup_quality") != "VALID_CANDIDATE":
        return "intentionally_weak_stock_probe"
    if level == "chaos":
        return "chaos_probe"
    return "exploratory_probe"


def _paper_exploration_reason(row: dict[str, Any], review: dict[str, Any] | None, contract: dict[str, Any], quality: str) -> list[str]:
    reasons = [
        f"Paper-only sample tagged as {quality}.",
        "Allowed because research mode needs both winners and losers.",
        "Not allowed for real cash unless normal cash gates pass later.",
    ]
    review_reason = (review or {}).get("reason")
    if review_reason:
        reasons.append(str(review_reason))
    for reason in row.get("reasons") or []:
        reasons.append(str(reason))
    return reasons[:8]


def _paper_exploration_underlying_reference(row: dict[str, Any]) -> float | None:
    signals = row.get("key_signals") or {}
    quote_summary = row.get("quote_summary") or row.get("quote") or {}
    candidates = [
        row.get("price"),
        row.get("entry_reference"),
        row.get("current_price"),
        row.get("last_price"),
        signals.get("price"),
        signals.get("last_price"),
        signals.get("close"),
        signals.get("current_price"),
        quote_summary.get("price") if isinstance(quote_summary, dict) else None,
        quote_summary.get("last_price") if isinstance(quote_summary, dict) else None,
    ]
    for value in candidates:
        parsed = _float_or_none_value(value)
        if parsed is not None and parsed > 0:
            return parsed
    return None


def _paper_exploration_entry_reference_from_item(service_container, item: dict[str, Any]) -> float | None:
    direct = _float_or_none_value(item.get("underlying_entry_reference"))
    if direct is not None and direct > 0:
        return direct
    entry_id = item.get("entry_event_id")
    if entry_id is None:
        return None
    for event in service_container.events.recent("manual_option_paper_entry", 500):
        if event.get("id") != entry_id:
            continue
        payload = event.get("payload") or {}
        entry_ref = _float_or_none_value(payload.get("underlying_entry_price"))
        if entry_ref is not None and entry_ref > 0:
            return entry_ref
        source = payload.get("source_preflight") or {}
        stock = source.get("stock_setup") or {}
        return _paper_exploration_underlying_reference(stock)
    return None


def _paper_exploration_trial_record(
    row: dict[str, Any],
    review: dict[str, Any] | None,
    contract: dict[str, Any] | None,
    status: str,
    contract_source: str | None,
    price_source: str | None,
) -> dict[str, Any]:
    ticker = str(row.get("ticker") or (review or {}).get("ticker") or "").upper()
    direction = _paper_exploration_direction(row)
    selected = contract or {}
    return {
        "status": status,
        "ticker": ticker,
        "stock_direction": direction,
        "option_direction": "call" if direction == "long" else "put" if direction == "short" else None,
        "stock_score": row.get("score"),
        "stock_status": row.get("status"),
        "stock_setup_quality": (row.get("quality_gates") or {}).get("stock_setup_quality"),
        "underlying_entry_reference": _paper_exploration_underlying_reference(row),
        "relative_volume": (row.get("key_signals") or {}).get("relative_volume"),
        "vwap_state": "above" if (row.get("key_signals") or {}).get("above_vwap") else "below" if (row.get("key_signals") or {}).get("below_vwap") else "unknown",
        "review_status": (review or {}).get("status"),
        "review_reason": (review or {}).get("reason"),
        "contract_symbol": selected.get("contract_symbol"),
        "contract_source": contract_source,
        "price_source": price_source,
        "ask": selected.get("ask"),
        "bid": selected.get("bid"),
        "spread_pct": selected.get("spread_pct"),
        "volume": selected.get("volume"),
        "open_interest": selected.get("open_interest"),
        "days_to_expiration": selected.get("days_to_expiration"),
        "max_loss_dollars": selected.get("max_loss_dollars"),
        "cash_eligible": False,
        "paper_only": True,
        "order_allowed": False,
    }


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


def _export_journal_checkpoint(service_container, limit: int = 500, event_types: list[str] | None = None) -> dict:
    limit = max(1, min(int(limit or 500), 2000))
    requested_types = [
        str(event_type).strip()
        for event_type in (event_types or [])
        if str(event_type).strip()
    ]
    if requested_types:
        events: list[dict[str, Any]] = []
        for event_type in requested_types:
            events.extend(service_container.events.recent(event_type, limit))
        events = sorted(events, key=lambda item: int(item.get("id") or 0), reverse=True)[:limit]
    else:
        events = service_container.events.recent(None, limit)
    counts = Counter(str(event.get("event_type") or "unknown") for event in events)
    latest_event_id = max([int(event.get("id") or 0) for event in events], default=0)
    checkpoint = {
        "status": "JOURNAL_CHECKPOINT_READY",
        "build_version": BUILD_VERSION,
        "exported_at": utc_now(),
        "limit": limit,
        "event_filter": requested_types,
        "event_count": len(events),
        "latest_event_id": latest_event_id,
        "event_type_counts": dict(counts),
        "events": events,
        "restore_guidance": [
            "Save this JSON if Render restarts or redeploys before the next review.",
            "Use the events as evidence for ChatGPT/Codex analysis and rule proposals.",
            "Do not treat a checkpoint as an execution record; it is local MCP journal evidence only.",
        ],
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "notes": "Checkpoint export only. It does not contact a broker and does not place, submit, simulate, modify, or cancel orders.",
    }
    checkpoint_event = service_container.events.log(
        "journal_checkpoint_export",
        {
            "status": "JOURNAL_CHECKPOINT_EXPORTED",
            "build_version": BUILD_VERSION,
            "exported_event_count": len(events),
            "latest_event_id": latest_event_id,
            "event_type_counts": dict(counts),
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        },
    )
    return {**checkpoint, "checkpoint_event_id": checkpoint_event.get("id")}


def _checkpoint_event_fingerprint(event: dict[str, Any]) -> str:
    payload = dict(event.get("payload") or {})
    payload.pop("_restored_from_checkpoint", None)
    source = {
        "id": event.get("id"),
        "timestamp": event.get("timestamp"),
        "event_type": event.get("event_type"),
        "payload": payload,
    }
    serialized = json.dumps(source, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _restore_journal_checkpoint(service_container, checkpoint: dict[str, Any], source_label: str = "manual_restore", max_events: int = 500) -> dict:
    max_events = max(1, min(int(max_events or 500), 2000))
    source_label = str(source_label or "manual_restore").strip()[:80] or "manual_restore"
    if not isinstance(checkpoint, dict):
        return {
            "status": "CHECKPOINT_RESTORE_REJECTED",
            "reason": "checkpoint must be an object",
            "restored_count": 0,
            "skipped_duplicate_count": 0,
            "invalid_count": 0,
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }
    raw_events = checkpoint.get("events")
    if not isinstance(raw_events, list):
        return {
            "status": "CHECKPOINT_RESTORE_REJECTED",
            "reason": "checkpoint.events must be a list",
            "restored_count": 0,
            "skipped_duplicate_count": 0,
            "invalid_count": 0,
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }

    existing_events = service_container.events.recent(None, 2000)
    existing_fingerprints: set[str] = set()
    for event in existing_events:
        payload = event.get("payload") or {}
        restored = payload.get("_restored_from_checkpoint") if isinstance(payload, dict) else None
        if isinstance(restored, dict) and restored.get("fingerprint"):
            existing_fingerprints.add(str(restored.get("fingerprint")))
        existing_fingerprints.add(_checkpoint_event_fingerprint(event))

    restored_events: list[dict[str, Any]] = []
    skipped_duplicates: list[dict[str, Any]] = []
    invalid_events: list[dict[str, Any]] = []
    for raw_event in raw_events[:max_events]:
        if not isinstance(raw_event, dict):
            invalid_events.append({"reason": "event is not an object"})
            continue
        event_type = str(raw_event.get("event_type") or "").strip()
        payload = raw_event.get("payload")
        if not event_type or not isinstance(payload, dict):
            invalid_events.append(
                {
                    "id": raw_event.get("id"),
                    "event_type": event_type or None,
                    "reason": "event_type and payload object are required",
                }
            )
            continue
        fingerprint = _checkpoint_event_fingerprint(raw_event)
        if fingerprint in existing_fingerprints:
            skipped_duplicates.append({"id": raw_event.get("id"), "event_type": event_type, "fingerprint": fingerprint})
            continue
        restored_payload = {
            **payload,
            "_restored_from_checkpoint": {
                "source_label": source_label,
                "original_id": raw_event.get("id"),
                "original_timestamp": raw_event.get("timestamp"),
                "fingerprint": fingerprint,
                "restored_build_version": BUILD_VERSION,
            },
        }
        restored = service_container.events.log(event_type, restored_payload)
        restored_events.append(
            {
                "id": restored.get("id"),
                "event_type": event_type,
                "original_id": raw_event.get("id"),
                "fingerprint": fingerprint,
            }
        )
        existing_fingerprints.add(fingerprint)

    counts = Counter(event["event_type"] for event in restored_events)
    status = "CHECKPOINT_RESTORE_READY" if restored_events else "CHECKPOINT_RESTORE_NO_NEW_EVENTS"
    payload = {
        "status": status,
        "build_version": BUILD_VERSION,
        "source_label": source_label,
        "checkpoint_build_version": checkpoint.get("build_version"),
        "checkpoint_exported_at": checkpoint.get("exported_at"),
        "requested_event_count": len(raw_events),
        "processed_event_count": min(len(raw_events), max_events),
        "restored_count": len(restored_events),
        "skipped_duplicate_count": len(skipped_duplicates),
        "invalid_count": len(invalid_events),
        "restored_event_type_counts": dict(counts),
        "restored_events": restored_events[:50],
        "skipped_duplicates": skipped_duplicates[:50],
        "invalid_events": invalid_events[:50],
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        "broker_action": False,
        "notes": [
            "Checkpoint restore rehydrates local MCP journal evidence only.",
            "Restored events are marked with _restored_from_checkpoint metadata.",
            "This is not broker proof and cannot place, submit, simulate, modify, or cancel orders.",
        ],
    }
    restore_event = service_container.events.log(
        "journal_checkpoint_restore",
        {
            "status": status,
            "build_version": BUILD_VERSION,
            "source_label": source_label,
            "checkpoint_build_version": checkpoint.get("build_version"),
            "restored_count": len(restored_events),
            "skipped_duplicate_count": len(skipped_duplicates),
            "invalid_count": len(invalid_events),
            "restored_event_type_counts": dict(counts),
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        },
    )
    return {**payload, "restore_event_id": restore_event.get("id")}


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


def _observer_row_summary(row: dict[str, Any]) -> dict[str, Any]:
    signals = row.get("key_signals") or {}
    quote = row.get("quote_summary") or {}
    evidence = row.get("evidence_packet") or {}
    confidence = evidence.get("data_confidence") or {}
    scorecard = signals.get("evidence_scorecard") or {}
    return {
        "ticker": row.get("ticker"),
        "status": row.get("status"),
        "score": row.get("score"),
        "confidence": row.get("confidence"),
        "direction": row.get("direction"),
        "data_status": row.get("data_status"),
        "entry_reference": quote.get("price"),
        "review_timestamp": quote.get("timestamp"),
        "quote_provider": quote.get("provider"),
        "quote_freshness_status": quote.get("freshness_status"),
        "relative_volume": signals.get("relative_volume"),
        "relative_volume_status": signals.get("relative_volume_status"),
        "vwap_state": "above" if signals.get("above_vwap") else "below" if signals.get("below_vwap") else "unknown",
        "relative_strength_label": (signals.get("relative_strength") or {}).get("label"),
        "data_confidence": confidence.get("status"),
        "data_confidence_score": confidence.get("score"),
        "data_flags": evidence.get("data_flags") or [],
        "missing_modules": evidence.get("missing_or_planned_modules") or scorecard.get("missing_or_planned_modules") or [],
        "reasons": row.get("reasons") or [],
    }


def _observer_pass_summary(row: dict[str, Any]) -> dict[str, Any]:
    summary = _observer_row_summary(row)
    reasons = summary.get("reasons") or []
    summary["primary_reason"] = reasons[0] if reasons else row.get("reason")
    return summary


def _observer_delta(service_container, current_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    previous = service_container.events.recent("market_open_observer", 1)
    if not previous:
        return {
            "status": "NO_PRIOR_OBSERVER",
            "new_candidate_tickers": [item.get("ticker") for item in current_candidates],
            "dropped_candidate_tickers": [],
            "persistent_candidate_tickers": [],
            "score_changes": [],
        }
    prior_payload = previous[0].get("payload") or {}
    prior_candidates = prior_payload.get("candidate_observations") or []
    prior_by_ticker = {str(item.get("ticker") or "").upper(): item for item in prior_candidates if isinstance(item, dict)}
    current_by_ticker = {str(item.get("ticker") or "").upper(): item for item in current_candidates if isinstance(item, dict)}
    prior_set = set(prior_by_ticker)
    current_set = set(current_by_ticker)
    score_changes = []
    for ticker in sorted(prior_set & current_set):
        old_score = _float_or_zero(prior_by_ticker[ticker].get("score"))
        new_score = _float_or_zero(current_by_ticker[ticker].get("score"))
        score_changes.append(
            {
                "ticker": ticker,
                "prior_score": old_score,
                "current_score": new_score,
                "change": round(new_score - old_score, 4),
                "prior_direction": prior_by_ticker[ticker].get("direction"),
                "current_direction": current_by_ticker[ticker].get("direction"),
            }
        )
    return {
        "status": "OBSERVER_DELTA_READY",
        "previous_event_id": previous[0].get("id"),
        "previous_timestamp": previous[0].get("timestamp"),
        "new_candidate_tickers": sorted(current_set - prior_set),
        "dropped_candidate_tickers": sorted(prior_set - current_set),
        "persistent_candidate_tickers": sorted(prior_set & current_set),
        "score_changes": score_changes,
    }


def _observer_followup_items(observations: list[dict[str, Any]], max_items: int, include_passes: bool) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for event in observations:
        payload = event.get("payload") or {}
        buckets = [("candidate", payload.get("candidate_observations") or [])]
        if include_passes:
            buckets.append(("pass", payload.get("pass_observations") or []))
        for bucket, rows in buckets:
            for row in rows:
                if not isinstance(row, dict):
                    continue
                ticker = str(row.get("ticker") or "").upper()
                entry = row.get("entry_reference")
                timestamp = row.get("review_timestamp")
                direction = _observer_followup_direction(row)
                if not ticker or not entry or not timestamp:
                    continue
                key = (ticker, str(entry), str(timestamp))
                if key in seen:
                    continue
                seen.add(key)
                status = row.get("status") or ("PASS" if bucket == "pass" else "CANDIDATE")
                snapshot = {
                    "ticker": ticker,
                    "status": status,
                    "direction": direction,
                    "score": row.get("score"),
                    "confidence": row.get("confidence"),
                    "reasons": row.get("reasons") or ([row.get("primary_reason")] if row.get("primary_reason") else []),
                    "key_signals": {
                        "relative_volume": row.get("relative_volume"),
                        "relative_volume_status": row.get("relative_volume_status"),
                    },
                    "quote_summary": {
                        "price": entry,
                        "timestamp": timestamp,
                        "provider": row.get("quote_provider"),
                        "freshness_status": row.get("quote_freshness_status"),
                    },
                    "evidence_packet": {
                        "data_flags": row.get("data_flags") or [],
                        "missing_or_planned_modules": row.get("missing_modules") or [],
                        "data_confidence": {"status": row.get("data_confidence"), "score": row.get("data_confidence_score")},
                    },
                    "quality_gates": {
                        "stock_setup_quality": "VALID_CANDIDATE" if bucket == "candidate" else "PASS",
                        "options_chain_quality": "NOT_VALIDATED",
                    },
                }
                items.append(
                    {
                        "review_id": f"observer-{event.get('id')}-{bucket}-{ticker}-{entry}",
                        "ticker": ticker,
                        "direction": direction,
                        "entry_reference": entry,
                        "review_timestamp": timestamp,
                        "source_observer_event_id": event.get("id"),
                        "source_observer_timestamp": event.get("timestamp"),
                        "source_bucket": bucket,
                        "snapshot": snapshot,
                    }
                )
                if len(items) >= max_items:
                    return items
    return items


def _observer_followup_direction(row: dict[str, Any]) -> str:
    raw = str(row.get("direction") or "").lower()
    if raw in {"short", "put", "puts", "bearish"}:
        return "short"
    if raw in {"long", "call", "calls", "bullish"}:
        return "long"
    vwap_state = str(row.get("vwap_state") or "").lower()
    if vwap_state == "below":
        return "short"
    return "long"


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


def _float_or_none_value(value: Any) -> float | None:
    try:
        if value is None or value != value or str(value).strip() == "":
            return None
        return float(value)
    except Exception:
        return None


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def _manual_action_is_close(action_type: str, order_status: str, side: str) -> bool:
    action = str(action_type or "").lower()
    status = str(order_status or "").lower()
    normalized_side = str(side or "").lower()
    close_markers = {"close", "closed", "exit", "sell_to_close", "stc", "filled_close", "manual_close"}
    if action in close_markers or normalized_side in {"sell", "sell_to_close", "stc", "close"}:
        return True
    return "close" in action or (status in {"filled", "executed", "complete", "completed"} and normalized_side.startswith("sell"))


def _manual_action_is_entry(action_type: str, order_status: str, side: str) -> bool:
    action = str(action_type or "").lower()
    status = str(order_status or "").lower()
    normalized_side = str(side or "").lower()
    entry_markers = {"buy", "open", "entry", "buy_to_open", "bto", "filled_entry", "manual_entry"}
    if action in entry_markers or normalized_side in {"buy", "buy_to_open", "bto", "open"}:
        return True
    return "open" in action or "entry" in action or (status in {"filled", "executed", "complete", "completed"} and normalized_side.startswith("buy"))


def _manual_broker_event_is_real_cash_close(event: dict[str, Any]) -> bool:
    payload = event.get("payload") or {}
    pnl = _float_or_none_value(payload.get("pnl_dollars"))
    return bool(payload.get("is_real_cash", True)) and bool(payload.get("is_closing_action")) and pnl is not None


def _manual_broker_event_is_real_cash_entry(event: dict[str, Any]) -> bool:
    payload = event.get("payload") or {}
    if not bool(payload.get("is_real_cash", True)):
        return False
    if payload.get("is_closing_action"):
        return False
    if payload.get("pending_buy"):
        return False
    action_type = str(payload.get("action_type") or "")
    order_status = str(payload.get("order_status") or "")
    side = str(payload.get("side") or "")
    if order_status not in {"filled", "executed", "complete", "completed", "open", "entry", "manual_entry"}:
        return False
    return _manual_action_is_entry(action_type, order_status, side)


def _event_local_date(event: dict[str, Any], timezone_name: str) -> str | None:
    timestamp = _parse_manual_action_time(event.get("timestamp"))
    if timestamp is None:
        payload = event.get("payload") or {}
        timestamp = _parse_manual_action_time(payload.get("exit_timestamp") or payload.get("entry_timestamp") or payload.get("timestamp"))
    if timestamp is None:
        return None
    try:
        return timestamp.astimezone(ZoneInfo(timezone_name)).date().isoformat()
    except Exception:
        return timestamp.astimezone(UTC).date().isoformat()


def _parse_manual_action_time(value: Any) -> datetime | None:
    try:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
        raw = str(value).strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = datetime.fromisoformat(raw)
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except Exception:
        return None


def _rules_hash() -> str:
    payload = {
        "build_version": BUILD_VERSION,
        "review_only": True,
        "no_market_orders": True,
        "manual_snapshot_required": True,
        "pending_recheck_seconds": 60,
        "truth_layer": "OptionSnapshotV2/DecisionRecordV2/OutcomeRecordV2",
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _manual_execution_receipt(
    action: dict[str, Any],
    submitted_at: str,
    broker_snapshot_ts: datetime | None,
    execution_ts: datetime | None,
    reviewed_price: float | None,
    fill_price: float | None,
    limit_price: float | None,
) -> dict[str, Any]:
    contract_symbol = str(action.get("contract_symbol") or action.get("symbol") or "")
    expected_contract_symbol = str(action.get("expected_contract_symbol") or action.get("reviewed_contract_symbol") or "")
    quantity = int(_float_or_zero(action.get("quantity")) or 1)
    mismatch_codes: list[str] = []
    if expected_contract_symbol and contract_symbol and expected_contract_symbol != contract_symbol:
        mismatch_codes.append("BROKER_CONTRACT_MISMATCH")
    if broker_snapshot_ts is None:
        mismatch_codes.append("BROKER_SNAPSHOT_TS_MISSING")
    if action.get("action_type") in {"filled", "manual_fill"} and execution_ts is None:
        mismatch_codes.append("EXECUTION_TS_MISSING")
    if fill_price is not None and limit_price is not None and fill_price > limit_price:
        mismatch_codes.append("FILL_ABOVE_LIMIT")
    price_drift = round(fill_price - reviewed_price, 4) if fill_price is not None and reviewed_price is not None else None
    if price_drift is not None and price_drift > 0:
        mismatch_codes.append("FILL_WORSE_THAN_REVIEWED_PRICE")
    reconciliation_status = "RECONCILED_USER_RECEIPT" if not mismatch_codes else "RECONCILIATION_NEEDS_REVIEW"
    return {
        "schema_version": "ManualExecutionReceiptV1",
        "receipt_id": hashlib.sha256(json.dumps(action, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16],
        "ticker": str(action.get("ticker") or action.get("underlying") or "").upper(),
        "contract_symbol": contract_symbol,
        "expected_contract_symbol": expected_contract_symbol or None,
        "quantity": quantity,
        "side": str(action.get("side") or "buy").lower(),
        "order_status": str(action.get("order_status") or action.get("status") or "").lower(),
        "submitted_at": submitted_at,
        "broker_snapshot_ts": broker_snapshot_ts.isoformat() if broker_snapshot_ts else None,
        "execution_ts": execution_ts.isoformat() if execution_ts else None,
        "reviewed_price": reviewed_price,
        "limit_price": limit_price,
        "fill_price": fill_price,
        "price_drift": price_drift,
        "screenshot_hash": action.get("screenshot_hash") or action.get("proof_hash"),
        "operator_id": action.get("operator_id") or "manual_operator",
        "reconciliation_status": reconciliation_status,
        "mismatch_codes": mismatch_codes,
        "notes": "User-reported receipt only; this MCP did not verify broker state or execute an order.",
    }


def _execution_outcome_label(entry: dict[str, Any], exit_value: float) -> str:
    drift = _float_or_zero(entry.get("price_drift"))
    if entry.get("option_snapshot_v2") and (entry.get("option_snapshot_v2") or {}).get("mismatch_codes"):
        return "EXECUTION_TRUTH_DIRTY"
    if drift > 0:
        return "EXECUTION_WORSE_THAN_REVIEW"
    if exit_value <= 0:
        return "EXECUTION_EXITED_WORTHLESS_OR_ZERO"
    return "EXECUTION_TRACKED_PAPER_ONLY"


def _manual_action_is_pending_buy(action_type: str, order_status: str, side: str) -> bool:
    if side not in {"buy", "opening_buy", "buy_to_open"}:
        return False
    joined = f"{action_type} {order_status}".lower()
    pending_words = {"pending", "queued", "new", "open", "submitted", "unconfirmed", "confirmed", "partially_filled", "working"}
    return any(word in joined for word in pending_words)


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
        "notes": "Crypto paper tools simulate and log only. They do not call a broker and cannot place broker orders.",
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
