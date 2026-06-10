from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from app.factory import create_container
from app.models.enums import Direction, OrderType
from app.models.schemas import TradePlan
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
        "options-structure mapping before changing live gates."
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
def analyze_ticker(ticker: str, mode: str | None = None) -> dict:
    return container.scanner.analyze_ticker(ticker, mode)


@mcp.tool
def validate_options_chain(ticker: str, direction: str = "call", max_contract_price: float | None = None) -> dict:
    return container.options.validate_chain(ticker, direction, max_contract_price)


@mcp.tool
def validate_broker_option_snapshot(snapshot: dict[str, Any], max_contract_price: float | None = None) -> dict:
    return container.options.validate_broker_snapshot(snapshot, max_contract_price)


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
