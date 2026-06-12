from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, time as day_time, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from fastmcp import Client


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "stock_bridge_state.json"
LOG_PATH = ROOT / "data" / "stock_bridge_loop.jsonl"
LIVE_AUTH_VALUE = "ENABLE_AGENTIC_STOCK_BRIDGE"


@dataclass(frozen=True)
class BridgeConfig:
    base_url: str
    mcp_url: str
    account_number: str
    live: bool
    interval_seconds: int
    once: bool
    min_score: float
    min_relative_volume: float
    max_spread_bps: float
    max_order_notional: float
    min_order_notional: float
    max_open_positions: int
    max_trades_per_day: int
    max_daily_loss: float
    stop_loss_pct: float
    take_profit_pct: float
    allowed_broker_alert_types: tuple[str, ...]
    account_value: float
    scan_max_candidates: int
    scan_review_top_n: int
    auth_timeout_seconds: int
    max_consecutive_errors: int
    error_cooldown_seconds: int
    market_hours: str


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def read_json_url(url: str, timeout: int = 90) -> dict[str, Any]:
    request = Request(url, headers={"accept": "application/json", "user-agent": "living-screener-stock-bridge/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json_url(url: str, payload: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"content-type": "application/json", "accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def append_log(event: dict[str, Any]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    event = {"timestamp": utc_now(), **event}
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True, default=str), encoding="utf-8")


def today_key() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def current_equity_session() -> str:
    now = datetime.now(ZoneInfo("America/New_York"))
    if now.weekday() >= 5:
        return "closed"
    current = now.time()
    if day_time(9, 30) <= current < day_time(16, 0):
        return "regular_hours"
    if day_time(4, 0) <= current < day_time(20, 0):
        return "extended_hours"
    return "closed"


def resolve_market_hours(config: BridgeConfig) -> str:
    configured = str(config.market_hours or "auto").strip().lower()
    if configured in {"regular_hours", "extended_hours", "all_day_hours"}:
        return configured
    session = current_equity_session()
    return "regular_hours" if session == "regular_hours" else "extended_hours"


def marketable_limit_price(side: str, quote: dict[str, Any], cushion_pct: float = 0.0015) -> float:
    bid = as_float(quote.get("bid_price"))
    ask = as_float(quote.get("ask_price"))
    last = as_float(quote.get("last_trade_price"))
    if side == "buy":
        ref = ask or last
        return round(ref * (1 + cushion_pct), 2) if ref > 0 else 0.0
    ref = bid or last
    return round(ref * (1 - cushion_pct), 2) if ref > 0 else 0.0


def whole_share_quantity(notional: float, limit_price: float) -> int:
    if notional <= 0 or limit_price <= 0:
        return 0
    return int(notional // limit_price)


def is_fractional_tradable(tradability: dict[str, Any]) -> bool:
    return str(tradability.get("fractional_tradability") or "").lower() == "tradable"


def new_entries_paused(state: dict[str, Any]) -> bool:
    paused_until = parse_timestamp(state.get("new_entries_paused_until"))
    if not paused_until:
        return False
    if paused_until.tzinfo is None:
        paused_until = paused_until.replace(tzinfo=UTC)
    if datetime.now(UTC) < paused_until.astimezone(UTC):
        return True
    state.pop("new_entries_paused_until", None)
    state.pop("pause_reason", None)
    state.pop("consecutive_errors", None)
    append_log({"event": "entry_pause_expired", "resumed_at": utc_now()})
    return False


def alert_types(order_checks: Any) -> list[str]:
    if not order_checks:
        return []
    if isinstance(order_checks, dict):
        alert_type = order_checks.get("alertType") or order_checks.get("alert_type")
        if alert_type:
            return [str(alert_type).upper()]
        return [str(key).upper() for key in order_checks.keys()]
    if isinstance(order_checks, list):
        found: list[str] = []
        for item in order_checks:
            found.extend(alert_types(item))
        return found
    return [str(order_checks).upper()]


def blocking_broker_alerts(order_checks: Any, allowed_alert_types: tuple[str, ...]) -> list[str]:
    allowed = {item.strip().upper() for item in allowed_alert_types if item.strip()}
    return [item for item in alert_types(order_checks) if item not in allowed]


def stock_intent_stop_risk_override_allowed(intent: dict[str, Any], notional: float, config: BridgeConfig) -> bool:
    reasons = [str(reason) for reason in (intent.get("blocking_reasons") or [])]
    if reasons != ["Proposed risk exceeds per-trade journal risk cap."]:
        return False
    stop_risk = round(notional * config.stop_loss_pct, 4)
    return 0 < stop_risk <= config.max_daily_loss and notional <= config.max_order_notional


def local_stock_intent_fallback(
    symbol: str,
    order_args: dict[str, str],
    notional: float,
    config: BridgeConfig,
    error: Exception,
) -> dict[str, Any] | None:
    estimated_stop_risk = round(notional * abs(config.stop_loss_pct), 4)
    max_fallback_risk = min(2.0, abs(config.max_daily_loss))
    if estimated_stop_risk <= 0 or estimated_stop_risk > max_fallback_risk:
        append_log(
            {
                "event": "intent_service_error_blocked",
                "symbol": symbol,
                "error": repr(error),
                "estimated_stop_risk": estimated_stop_risk,
                "max_fallback_risk": max_fallback_risk,
            }
        )
        return None

    ticket = {
        "account_number": order_args.get("account_number", ""),
        "asset_class": "equity",
        "symbol": symbol,
        "side": order_args.get("side", ""),
        "type": order_args.get("type", ""),
        "quantity": order_args.get("quantity", ""),
        "dollar_amount": order_args.get("dollar_amount", ""),
        "limit_price": order_args.get("limit_price", ""),
        "time_in_force": order_args.get("time_in_force", "gfd"),
        "market_hours": order_args.get("market_hours", "regular_hours"),
    }
    canonical = json.dumps(ticket, sort_keys=True, separators=(",", ":"))
    intent_hash = "local_fallback_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    intent = {
        "status": "STOCK_EXECUTION_INTENT_READY",
        "intent_hash": intent_hash,
        "ticket": ticket,
        "canonical_ticket_json": canonical,
        "robinhood_review_equity_order_args": order_args,
        "estimated_max_risk_dollars": round(estimated_stop_risk, 2),
        "warnings": ["Using local bridge intent fallback because remote /trade/stock-intent returned an error."],
    }
    append_log(
        {
            "event": "intent_service_error_local_fallback",
            "symbol": symbol,
            "error": repr(error),
            "intent_hash": intent_hash,
            "estimated_stop_risk": estimated_stop_risk,
        }
    )
    return intent


def fetch_stock_intent(
    config: BridgeConfig,
    ticket_query: str,
    symbol: str,
    order_args: dict[str, str],
    notional: float,
) -> dict[str, Any] | None:
    try:
        return read_json_url(f"{config.base_url.rstrip('/')}/trade/stock-intent?{ticket_query}", timeout=30).get("result") or {}
    except Exception as exc:  # noqa: BLE001 - bridge should keep cycling through transient service errors
        return local_stock_intent_fallback(symbol, order_args, notional, config, exc)


def broker_setup_blocker(error_text: str) -> bool:
    lowered = error_text.lower()
    return "investment_profile" in lowered or "investing goals" in lowered or "second trade" in lowered


def tool_payload(result: Any) -> Any:
    """Normalize FastMCP tool results across structured and text outputs."""
    if isinstance(result, dict):
        return result.get("data", result)
    structured = getattr(result, "structured_content", None)
    if structured:
        return structured.get("data", structured) if isinstance(structured, dict) else structured
    if hasattr(result, "model_dump"):
        dumped = result.model_dump()
        if isinstance(dumped, dict):
            return dumped.get("data", dumped)
    root = getattr(result, "root", None)
    if isinstance(root, dict):
        return root.get("data", root)
    data = getattr(result, "data", None)
    if data is not None:
        if hasattr(data, "model_dump"):
            dumped = data.model_dump()
            if isinstance(dumped, dict):
                return dumped.get("data", dumped)
        return data
    if isinstance(result, list) and result:
        text = getattr(result[0], "text", None)
        if text:
            try:
                parsed = json.loads(text)
                return parsed.get("data", parsed) if isinstance(parsed, dict) else parsed
            except json.JSONDecodeError:
                return {"text": text}
    content = getattr(result, "content", None)
    if content:
        text = getattr(content[0], "text", None)
        if text:
            try:
                parsed = json.loads(text)
                return parsed.get("data", parsed) if isinstance(parsed, dict) else parsed
            except json.JSONDecodeError:
                return {"text": text}
    return result


class RobinhoodBroker:
    def __init__(self, config: BridgeConfig):
        self.config = config
        self.client = Client(config.mcp_url, auth="oauth", timeout=config.auth_timeout_seconds)
        self.tools: set[str] = set()

    async def __aenter__(self) -> "RobinhoodBroker":
        await self.client.__aenter__()
        tools = await self.client.list_tools()
        self.tools = {str(getattr(tool, "name", "")) for tool in tools}
        required = {"get_portfolio", "get_equity_positions", "get_equity_orders", "get_equity_quotes", "get_equity_tradability", "review_equity_order", "place_equity_order", "cancel_equity_order"}
        missing = sorted(required - self.tools)
        if missing:
            raise RuntimeError(f"Robinhood MCP missing required equity tools: {', '.join(missing)}")
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.client.__aexit__(exc_type, exc, tb)

    async def call(self, name: str, args: dict[str, Any] | None = None) -> Any:
        result = await self.client.call_tool(name, args or {}, timeout=self.config.auth_timeout_seconds)
        return tool_payload(result)

    async def portfolio(self) -> dict[str, Any]:
        return await self.call("get_portfolio", {"account_number": self.config.account_number})

    async def positions(self) -> list[dict[str, Any]]:
        payload = await self.call("get_equity_positions", {"account_number": self.config.account_number})
        return list((payload or {}).get("positions") or [])

    async def orders_today(self) -> list[dict[str, Any]]:
        start_utc = datetime.now(UTC).strftime("%Y-%m-%dT05:00:00Z")
        payload = await self.call("get_equity_orders", {"account_number": self.config.account_number, "created_at_gte": start_utc})
        return list((payload or {}).get("orders") or [])

    async def quotes(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        payload = await self.call("get_equity_quotes", {"symbols": symbols[:20]})
        rows = (payload or {}).get("results") or []
        return {str((row.get("quote") or {}).get("symbol") or "").upper(): row.get("quote") or {} for row in rows}

    async def tradability(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        payload = await self.call("get_equity_tradability", {"account_number": self.config.account_number, "symbols": symbols[:10]})
        rows = (payload or {}).get("results") or []
        return {str(row.get("symbol") or "").upper(): row for row in rows}

    async def review_order(self, args: dict[str, Any]) -> dict[str, Any]:
        return await self.call("review_equity_order", args)

    async def place_order(self, args: dict[str, Any]) -> dict[str, Any]:
        return await self.call("place_equity_order", args)


def scan_candidates(config: BridgeConfig) -> list[dict[str, Any]]:
    query = urlencode(
        {
            "account_value": config.account_value,
            "max_candidates": config.scan_max_candidates,
            "review_top_n": config.scan_review_top_n,
            "include_event_context": "true",
            "format": "json",
        }
    )
    data = read_json_url(f"{config.base_url.rstrip('/')}/ops/broad-opportunity-scan?{query}", timeout=100)
    result = data.get("result") or {}
    append_log(
        {
            "event": "scan_complete",
            "status": result.get("status"),
            "stock_candidate_count": result.get("stock_candidate_count"),
            "options_review_count": result.get("options_review_count"),
            "event_candidate_count": result.get("event_candidate_count"),
        }
    )
    return list(result.get("stock_review_candidates") or [])


def select_long_candidate(
    candidates: list[dict[str, Any]],
    quotes: dict[str, dict[str, Any]],
    tradability: dict[str, dict[str, Any]],
    held_symbols: set[str],
    config: BridgeConfig,
) -> dict[str, Any] | None:
    ranked = sorted(candidates, key=lambda row: (as_float(row.get("stock_score")), as_float(row.get("relative_volume"))), reverse=True)
    for row in ranked:
        symbol = str(row.get("ticker") or "").upper()
        if not symbol or symbol in held_symbols:
            continue
        if str(row.get("stock_direction") or "").lower() != "long":
            continue
        if str(row.get("stock_setup_quality") or "") != "VALID_CANDIDATE":
            continue
        if as_float(row.get("stock_score")) < config.min_score:
            continue
        if as_float(row.get("relative_volume")) < config.min_relative_volume:
            continue
        if str(row.get("vwap_state") or "").lower() != "above":
            continue
        trade = tradability.get(symbol) or {}
        if not trade.get("tradeable") or trade.get("state") != "active":
            continue
        quote = quotes.get(symbol) or {}
        bid = as_float(quote.get("bid_price"))
        ask = as_float(quote.get("ask_price"))
        last = as_float(quote.get("last_trade_price"))
        ref = ask or last
        if ref <= 0 or bid <= 0 or ask <= 0:
            continue
        spread_bps = ((ask - bid) / ref) * 10000
        if spread_bps > config.max_spread_bps:
            append_log({"event": "candidate_rejected", "symbol": symbol, "reason": "spread_too_wide", "spread_bps": round(spread_bps, 2)})
            continue
        return {"scan": row, "quote": quote, "tradability": trade, "spread_bps": spread_bps}
    return None


def position_value(position: dict[str, Any], quote: dict[str, Any]) -> float:
    qty = as_float(position.get("quantity"))
    last = as_float(quote.get("last_trade_price"))
    return qty * last


async def manage_positions(broker: RobinhoodBroker, config: BridgeConfig, state: dict[str, Any]) -> None:
    positions = await broker.positions()
    symbols = [str(pos.get("symbol") or "").upper() for pos in positions if pos.get("symbol")]
    if not symbols:
        return
    quotes = await broker.quotes(symbols)
    for pos in positions:
        symbol = str(pos.get("symbol") or "").upper()
        qty = as_float(pos.get("shares_available_for_sells") or pos.get("quantity"))
        avg = as_float(pos.get("average_buy_price"))
        last = as_float((quotes.get(symbol) or {}).get("last_trade_price"))
        if not symbol or qty <= 0 or avg <= 0 or last <= 0:
            continue
        pnl_pct = (last - avg) / avg
        exit_reason = None
        if pnl_pct <= -abs(config.stop_loss_pct):
            exit_reason = "stop_loss"
        elif pnl_pct >= abs(config.take_profit_pct):
            exit_reason = "take_profit"
        if not exit_reason:
            continue
        market_hours = resolve_market_hours(config)
        if market_hours == "regular_hours":
            args = {
                "account_number": config.account_number,
                "symbol": symbol,
                "side": "sell",
                "type": "market",
                "quantity": f"{qty:.6f}",
                "time_in_force": "gfd",
                "market_hours": "regular_hours",
            }
        else:
            if abs(qty - round(qty)) > 0.000001:
                append_log(
                    {
                        "event": "exit_skipped_extended_fractional_not_supported",
                        "symbol": symbol,
                        "quantity": qty,
                        "reason": exit_reason,
                        "market_hours": market_hours,
                        "note": "Robinhood equity tool supports fractional market orders in regular hours; extended-hours fractional exits may be rejected.",
                    }
                )
                continue
            limit_price = marketable_limit_price("sell", quotes.get(symbol) or {})
            if limit_price <= 0:
                append_log({"event": "exit_skipped_no_extended_limit_price", "symbol": symbol, "reason": exit_reason})
                continue
            args = {
                "account_number": config.account_number,
                "symbol": symbol,
                "side": "sell",
                "type": "limit",
                "quantity": str(int(round(qty))),
                "limit_price": f"{limit_price:.2f}",
                "time_in_force": "gfd",
                "market_hours": market_hours,
            }
        review = await broker.review_order(args)
        append_log({"event": "exit_review", "symbol": symbol, "reason": exit_reason, "pnl_pct": pnl_pct, "review": review})
        if not config.live:
            continue
        place_args = {**args, "ref_id": str(uuid.uuid4())}
        placed = await broker.place_order(place_args)
        append_log({"event": "exit_placed", "symbol": symbol, "reason": exit_reason, "order": placed})
        log_broker_action(
            config,
            {
                "ticker": symbol,
                "action_type": "agentic_bridge_exit",
                "order_status": ((placed.get("order") or {}).get("state") if isinstance(placed, dict) else None) or "submitted",
                "side": "sell",
                "direction": "long",
                "fill_price": last,
                "quantity": qty,
                "execution_ts": utc_now(),
                "mode": "stock_bridge_loop",
                "notes": f"exit_reason={exit_reason}; pnl_pct={pnl_pct:.6f}",
            },
        )


def build_entry_order_args(config: BridgeConfig, selected: dict[str, Any], notional: float, buying_power: float) -> tuple[dict[str, str] | None, str | None]:
    symbol = selected["scan"]["ticker"].upper()
    market_hours = resolve_market_hours(config)
    if current_equity_session() == "closed" and market_hours == "extended_hours":
        return None, "equity_market_closed"
    quote = selected.get("quote") or {}
    trade = selected.get("tradability") or {}
    if market_hours == "regular_hours":
        if not is_fractional_tradable(trade):
            ref_price = as_float(quote.get("ask_price")) or as_float(quote.get("last_trade_price"))
            quantity = whole_share_quantity(min(notional, buying_power), ref_price)
            if ref_price <= 0:
                return None, "non_fractional_symbol_has_no_valid_reference_price"
            if quantity < 1:
                return None, f"regular_hours_non_fractional_symbol_requires_whole_share_but_budget_{notional:.2f}_is_below_price_{ref_price:.2f}"
            return (
                {
                    "account_number": config.account_number,
                    "symbol": symbol,
                    "side": "buy",
                    "type": "market",
                    "quantity": str(quantity),
                    "time_in_force": "gfd",
                    "market_hours": "regular_hours",
                },
                None,
            )
        return (
            {
                "account_number": config.account_number,
                "symbol": symbol,
                "side": "buy",
                "type": "market",
                "dollar_amount": f"{notional:.2f}",
                "time_in_force": "gfd",
                "market_hours": "regular_hours",
            },
            None,
        )
    limit_price = marketable_limit_price("buy", quote)
    quantity = whole_share_quantity(min(notional, buying_power), limit_price)
    if limit_price <= 0:
        return None, "no_valid_extended_limit_price"
    if quantity < 1:
        return None, f"extended_hours_requires_whole_share_limit_order_but_budget_{notional:.2f}_is_below_limit_{limit_price:.2f}"
    return (
        {
            "account_number": config.account_number,
            "symbol": symbol,
            "side": "buy",
            "type": "limit",
            "quantity": str(quantity),
            "limit_price": f"{limit_price:.2f}",
            "time_in_force": "gfd",
            "market_hours": market_hours,
        },
        None,
    )


def log_broker_action(config: BridgeConfig, payload: dict[str, Any]) -> None:
    try:
        payload = {"is_options_order": False, "is_real_cash": True, **payload}
        post_json_url(f"{config.base_url.rstrip('/')}/trade/manual-action", payload, timeout=30)
    except Exception as exc:  # noqa: BLE001 - logging must not kill executor
        append_log({"event": "journal_log_failed", "error": repr(exc), "payload": payload})


def state_for_today(state: dict[str, Any], portfolio: dict[str, Any]) -> dict[str, Any]:
    key = today_key()
    if state.get("date") != key:
        state.clear()
        state.update(
            {
                "date": key,
                "day_start_value": as_float(portfolio.get("total_value")),
                "trade_count": 0,
                "halted": False,
                "last_order_ids": [],
            }
        )
    return state


async def run_cycle(broker: RobinhoodBroker, config: BridgeConfig, state: dict[str, Any]) -> None:
    portfolio = await broker.portfolio()
    state_for_today(state, portfolio)
    total_value = as_float(portfolio.get("total_value"))
    buying_power = as_float(((portfolio.get("buying_power") or {}).get("buying_power")))
    day_start = as_float(state.get("day_start_value"), total_value)
    drawdown = max(0.0, day_start - total_value)
    if drawdown >= config.max_daily_loss:
        state["halted"] = True
        append_log({"event": "halted_daily_loss", "day_start_value": day_start, "total_value": total_value, "drawdown": drawdown})
        await manage_positions(broker, config, state)
        save_state(state)
        return
    state["halted"] = False
    await manage_positions(broker, config, state)
    if new_entries_paused(state):
        append_log(
            {
                "event": "entry_paused_cooldown",
                "pause_reason": state.get("pause_reason"),
                "new_entries_paused_until": state.get("new_entries_paused_until"),
            }
        )
        save_state(state)
        return
    positions = await broker.positions()
    open_symbols = {str(pos.get("symbol") or "").upper() for pos in positions if as_float(pos.get("quantity")) > 0}
    open_orders = [order for order in await broker.orders_today() if str(order.get("state") or "").lower() in {"new", "queued", "confirmed", "unconfirmed", "partially_filled"}]
    if len(open_symbols) >= config.max_open_positions or open_orders:
        append_log({"event": "entry_skipped_capacity", "open_symbols": sorted(open_symbols), "open_order_count": len(open_orders)})
        save_state(state)
        return
    if int(state.get("trade_count") or 0) >= config.max_trades_per_day:
        append_log({"event": "entry_skipped_trade_count", "trade_count": state.get("trade_count")})
        save_state(state)
        return
    notional = min(config.max_order_notional, buying_power)
    if notional < config.min_order_notional:
        append_log({"event": "entry_skipped_buying_power", "buying_power": buying_power, "min_order_notional": config.min_order_notional})
        save_state(state)
        return
    candidates = scan_candidates(config)
    symbols = [str(row.get("ticker") or "").upper() for row in candidates if row.get("ticker")]
    quotes = await broker.quotes(symbols[:20])
    tradability = await broker.tradability(symbols[:10])
    selected = select_long_candidate(candidates, quotes, tradability, open_symbols, config)
    if not selected:
        append_log({"event": "no_trade", "reason": "no_long_candidate_passed_bridge_filters"})
        save_state(state)
        return
    symbol = selected["scan"]["ticker"].upper()
    order_args, skip_reason = build_entry_order_args(config, selected, notional, buying_power)
    if not order_args:
        append_log({"event": "entry_skipped_order_shape", "symbol": symbol, "reason": skip_reason})
        save_state(state)
        return
    ticket_query = urlencode(
        {
            "account_number": config.account_number,
            "symbol": symbol,
            "side": order_args["side"],
            "order_type": order_args["type"],
            "quantity": order_args.get("quantity", ""),
            "dollar_amount": order_args.get("dollar_amount", ""),
            "limit_price": order_args.get("limit_price", ""),
            "time_in_force": order_args.get("time_in_force", "gfd"),
            "market_hours": order_args.get("market_hours", "regular_hours"),
            "account_value": config.account_value,
            "buying_power": buying_power,
            "max_daily_loss": config.max_daily_loss,
            "stop_loss_pct": config.stop_loss_pct,
        }
    )
    intent = fetch_stock_intent(config, ticket_query, symbol, order_args, notional)
    if not intent:
        save_state(state)
        return
    if intent.get("status") != "STOCK_EXECUTION_INTENT_READY":
        if stock_intent_stop_risk_override_allowed(intent, notional, config):
            append_log(
                {
                    "event": "intent_notional_risk_override",
                    "symbol": symbol,
                    "notional": notional,
                    "estimated_stop_risk": round(notional * config.stop_loss_pct, 4),
                    "intent": intent,
                }
            )
        else:
            append_log({"event": "intent_blocked", "symbol": symbol, "intent": intent})
            save_state(state)
            return
    order_args = intent.get("robinhood_review_equity_order_args") or order_args
    review = await broker.review_order(order_args)
    append_log({"event": "entry_review", "symbol": symbol, "notional": notional, "intent_hash": intent.get("intent_hash"), "review": review})
    checks = review.get("order_checks") if isinstance(review, dict) else None
    if checks:
        blocking = blocking_broker_alerts(checks, config.allowed_broker_alert_types)
        if blocking:
            append_log({"event": "entry_rejected_broker_checks", "symbol": symbol, "blocking_alerts": blocking, "order_checks": checks})
            save_state(state)
            return
        append_log({"event": "entry_allowed_broker_checks", "symbol": symbol, "allowed_alerts": alert_types(checks), "order_checks": checks})
    if not config.live:
        append_log({"event": "entry_dry_run_ready", "symbol": symbol, "order_args": order_args})
        save_state(state)
        return
    place_args = {**order_args, "ref_id": str(uuid.uuid4())}
    placed = await broker.place_order(place_args)
    order = placed.get("order") if isinstance(placed, dict) else {}
    state["trade_count"] = int(state.get("trade_count") or 0) + 1
    state.setdefault("last_order_ids", []).append(order.get("id"))
    append_log({"event": "entry_placed", "symbol": symbol, "intent_hash": intent.get("intent_hash"), "order": placed})
    log_broker_action(
        config,
        {
            "ticker": symbol,
            "action_type": "agentic_bridge_order",
            "order_status": order.get("state") or "submitted",
            "side": "buy",
            "direction": "long",
            "reviewed_price": as_float((review.get("quote_data") or {}).get("ask_price")) if isinstance(review, dict) else None,
            "fill_price": as_float(order.get("average_price") or order.get("price")) if isinstance(order, dict) else None,
            "quantity": as_float(order.get("cumulative_quantity") or order.get("quantity")) if isinstance(order, dict) else 1,
            "submitted_at": order.get("created_at") if isinstance(order, dict) else utc_now(),
            "execution_ts": order.get("last_transaction_at") if isinstance(order, dict) else utc_now(),
            "mode": "stock_bridge_loop",
            "notes": f"order_id={order.get('id')}; dollar_amount={notional:.2f}; intent_hash={intent.get('intent_hash')}",
        },
    )
    save_state(state)


def parse_args(argv: list[str]) -> BridgeConfig:
    parser = argparse.ArgumentParser(description="Living Screener local Robinhood stock bridge loop")
    parser.add_argument("--base-url", default=os.getenv("SCREENER_BASE_URL", "https://living-screener-mcp.onrender.com"))
    parser.add_argument("--mcp-url", default=os.getenv("ROBINHOOD_MCP_URL", "https://agent.robinhood.com/mcp/trading"))
    parser.add_argument("--account-number", default=os.getenv("ROBINHOOD_ACCOUNT_NUMBER", "628006199"))
    parser.add_argument("--live", action="store_true", default=as_bool(os.getenv("STOCK_BRIDGE_LIVE", "false")))
    parser.add_argument("--interval-seconds", type=int, default=int(os.getenv("STOCK_BRIDGE_INTERVAL_SECONDS", "60")))
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--min-score", type=float, default=float(os.getenv("STOCK_BRIDGE_MIN_SCORE", "76")))
    parser.add_argument("--min-relative-volume", type=float, default=float(os.getenv("STOCK_BRIDGE_MIN_RELATIVE_VOLUME", "0.45")))
    parser.add_argument("--max-spread-bps", type=float, default=float(os.getenv("STOCK_BRIDGE_MAX_SPREAD_BPS", "35")))
    parser.add_argument("--max-order-notional", type=float, default=float(os.getenv("STOCK_BRIDGE_MAX_ORDER_NOTIONAL", "10")))
    parser.add_argument("--min-order-notional", type=float, default=float(os.getenv("STOCK_BRIDGE_MIN_ORDER_NOTIONAL", "1")))
    parser.add_argument("--max-open-positions", type=int, default=int(os.getenv("STOCK_BRIDGE_MAX_OPEN_POSITIONS", "3")))
    parser.add_argument("--max-trades-per-day", type=int, default=int(os.getenv("STOCK_BRIDGE_MAX_TRADES_PER_DAY", "10")))
    parser.add_argument("--max-daily-loss", type=float, default=float(os.getenv("STOCK_BRIDGE_MAX_DAILY_LOSS", "20")))
    parser.add_argument("--stop-loss-pct", type=float, default=float(os.getenv("STOCK_BRIDGE_STOP_LOSS_PCT", "0.0035")))
    parser.add_argument("--take-profit-pct", type=float, default=float(os.getenv("STOCK_BRIDGE_TAKE_PROFIT_PCT", "0.0045")))
    parser.add_argument("--allowed-broker-alert-types", default=os.getenv("STOCK_BRIDGE_ALLOWED_BROKER_ALERT_TYPES", "EQUITY_SUITABILITY"))
    parser.add_argument("--account-value", type=float, default=float(os.getenv("STOCK_BRIDGE_ACCOUNT_VALUE", "100")))
    parser.add_argument("--scan-max-candidates", type=int, default=int(os.getenv("STOCK_BRIDGE_SCAN_MAX_CANDIDATES", "60")))
    parser.add_argument("--scan-review-top-n", type=int, default=int(os.getenv("STOCK_BRIDGE_SCAN_REVIEW_TOP_N", "20")))
    parser.add_argument("--auth-timeout-seconds", type=int, default=int(os.getenv("STOCK_BRIDGE_AUTH_TIMEOUT_SECONDS", "300")))
    parser.add_argument("--max-consecutive-errors", type=int, default=int(os.getenv("STOCK_BRIDGE_MAX_CONSECUTIVE_ERRORS", "2")))
    parser.add_argument("--error-cooldown-seconds", type=int, default=int(os.getenv("STOCK_BRIDGE_ERROR_COOLDOWN_SECONDS", "300")))
    parser.add_argument("--market-hours", default=os.getenv("STOCK_BRIDGE_MARKET_HOURS", "auto"))
    args = parser.parse_args(argv)
    raw = vars(args)
    raw["allowed_broker_alert_types"] = tuple(
        item.strip().upper()
        for item in str(raw["allowed_broker_alert_types"]).split(",")
        if item.strip()
    )
    config = BridgeConfig(**raw)
    if config.live and os.getenv("STOCK_BRIDGE_LIVE_AUTH") != LIVE_AUTH_VALUE:
        raise SystemExit(
            "Live mode refused. Set STOCK_BRIDGE_LIVE_AUTH=ENABLE_AGENTIC_STOCK_BRIDGE "
            "to acknowledge real-money autonomous trading risk."
        )
    return config


async def async_main(argv: list[str]) -> int:
    config = parse_args(argv)
    append_log({"event": "bridge_start", "config": {**asdict(config), "account_number": "***"}})
    print(f"Living Screener stock bridge loop | live={config.live} | account={config.account_number} | base={config.base_url}")
    print(f"Logs: {LOG_PATH}")
    print(f"State: {STATE_PATH}")
    print("If OAuth opens a Robinhood URL, approve it in the browser to connect the local executor.")
    state = load_state()
    consecutive_errors = 0
    async with RobinhoodBroker(config) as broker:
        while True:
            try:
                await run_cycle(broker, config, state)
                consecutive_errors = 0
            except Exception as exc:  # noqa: BLE001 - fail one cycle, not the process
                error_text = repr(exc)
                consecutive_errors += 1
                append_log({"event": "cycle_error", "error": error_text, "consecutive_errors": consecutive_errors})
                if broker_setup_blocker(error_text):
                    state["halted"] = True
                    state["halt_reason"] = "broker_investment_profile_required"
                    state["halted_at"] = utc_now()
                    save_state(state)
                    append_log({
                        "event": "bridge_halted_broker_profile_required",
                        "account_number": config.account_number,
                        "next_action": "Complete the Robinhood investment profile for the agentic account before restarting live bridge.",
                    })
                    print("Bridge halted: Robinhood requires the investment profile before additional trades.", file=sys.stderr)
                    break
                if consecutive_errors >= config.max_consecutive_errors:
                    pause_until = datetime.now(UTC) + timedelta(seconds=max(1, config.error_cooldown_seconds))
                    state["halted"] = False
                    state["pause_reason"] = "consecutive_data_or_broker_errors"
                    state["new_entries_paused_until"] = pause_until.isoformat()
                    state["consecutive_errors"] = consecutive_errors
                    save_state(state)
                    append_log(
                        {
                            "event": "bridge_entry_pause_consecutive_errors",
                            "consecutive_errors": consecutive_errors,
                            "max_consecutive_errors": config.max_consecutive_errors,
                            "cooldown_seconds": config.error_cooldown_seconds,
                            "new_entries_paused_until": pause_until.isoformat(),
                            "next_action": "Bridge remains alive, manages positions, and resumes new-entry scanning after cooldown if health recovers.",
                        }
                    )
                    print("Bridge paused new entries: consecutive data or broker errors reached the configured limit.", file=sys.stderr)
                    consecutive_errors = 0
                print(f"[{utc_now()}] cycle_error: {exc}", file=sys.stderr)
            if config.once:
                break
            time.sleep(config.interval_seconds)
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(async_main(sys.argv[1:])))


if __name__ == "__main__":
    main()
