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
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from fastmcp import Client


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.paper_lifecycle_ledger import record_entry as record_paper_lifecycle_entry
from tools.paper_lifecycle_ledger import record_exit as record_paper_lifecycle_exit

STATE_PATH = ROOT / "data" / "stock_bridge_state.json"
LOG_PATH = ROOT / "data" / "stock_bridge_loop.jsonl"
READINESS_GATES_PATH = ROOT / "config" / "autonomous_readiness_gates.json"
LIVE_AUTH_VALUE = "ENABLE_AGENTIC_STOCK_BRIDGE"
ALLOWED_LIVE_STAGE = "stage_3_human_approved_live_trades"


@dataclass(frozen=True)
class BridgeConfig:
    broker: str
    base_url: str
    mcp_url: str
    account_number: str
    alpaca_base_url: str
    alpaca_data_url: str
    alpaca_api_key_id: str
    alpaca_api_secret_key: str
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
    enable_crypto_execution: bool
    allow_market_options: bool
    allow_market_crypto: bool
    max_option_contract_cost: float
    max_option_account_risk: float


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


def request_json_url(
    url: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request_headers = {"accept": "application/json", "user-agent": "living-screener-stock-bridge/1.0"}
    if payload is not None:
        request_headers["content-type"] = "application/json"
    request_headers.update(headers or {})
    request = Request(url, data=body, headers=request_headers, method=method)
    with urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


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


def load_readiness_gates() -> dict[str, Any]:
    try:
        return json.loads(READINESS_GATES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Live mode refused. Readiness gates could not be loaded: {exc}") from exc


def requested_autonomy_stage() -> str:
    return os.getenv("AUTONOMY_STAGE", ALLOWED_LIVE_STAGE).strip() or ALLOWED_LIVE_STAGE


def alpaca_endpoint_environment(base_url: str) -> str:
    normalized = normalize_trading_base_url(base_url).lower()
    if "paper-api.alpaca.markets" in normalized:
        return "paper"
    if "api.alpaca.markets" in normalized:
        return "live"
    return "custom"


def is_alpaca_paper_submission(live: bool, broker: str, alpaca_base_url: str, stage: str | None = None) -> bool:
    resolved_stage = stage if stage is not None else requested_autonomy_stage()
    return (
        live
        and broker == "alpaca"
        and resolved_stage == "stage_2_paper_trading_automation"
        and alpaca_endpoint_environment(alpaca_base_url) == "paper"
    )


def enforce_live_readiness_gate(live: bool, broker: str = "robinhood", alpaca_base_url: str = "") -> None:
    gates = load_readiness_gates()
    if gates.get("global_live_default") is not False:
        raise SystemExit("Live mode refused. Readiness gates must keep global_live_default=false.")
    stage = requested_autonomy_stage()
    stage_limits = gates.get("stage_limits") or {}
    if stage not in stage_limits:
        raise SystemExit(f"Live mode refused. Unknown AUTONOMY_STAGE={stage!r}.")
    if is_alpaca_paper_submission(live, broker, alpaca_base_url, stage):
        return
    if live and stage != ALLOWED_LIVE_STAGE:
        raise SystemExit(
            "Live mode refused. The bridge currently permits only "
            f"{ALLOWED_LIVE_STAGE}; requested {stage}. Full or limited autonomous live trading remains blocked "
            "until readiness gates, monitoring, paper sample size, reconciliation, and operator runbooks are satisfied."
        )
    if live and not stage_limits.get(stage, {}).get("human_required"):
        raise SystemExit("Live mode refused. Current live bridge requires human-approved Stage 3 operation.")
    if live and broker == "alpaca":
        raise SystemExit(
            "Live mode refused. Stage 3 is currently scoped to small, human-supervised Robinhood equity orders only. "
            "Alpaca remains approved for paper automation until separate Alpaca live-cash readiness is proven."
        )


def enforce_live_config_caps(config: BridgeConfig) -> None:
    if not config.live or is_alpaca_paper_submission(config.live, config.broker, config.alpaca_base_url):
        return
    gates = load_readiness_gates()
    stage = requested_autonomy_stage()
    stage_limit = (gates.get("stage_limits") or {}).get(stage) or {}
    max_order_notional = as_float(stage_limit.get("max_order_notional_usd"))
    max_daily_loss = as_float(stage_limit.get("max_daily_loss_usd"))
    if max_order_notional > 0 and config.max_order_notional > max_order_notional:
        raise SystemExit(
            f"Live mode refused. Stage 3 max_order_notional ${config.max_order_notional:.2f} exceeds "
            f"configured cap ${max_order_notional:.2f}."
        )
    if max_daily_loss > 0 and config.max_daily_loss > max_daily_loss:
        raise SystemExit(
            f"Live mode refused. Stage 3 max_daily_loss ${config.max_daily_loss:.2f} exceeds "
            f"configured cap ${max_daily_loss:.2f}."
        )


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


def normalize_trading_base_url(base_url: str) -> str:
    cleaned = str(base_url or "").strip().rstrip("/")
    if cleaned.lower().endswith("/v2"):
        return cleaned[:-3].rstrip("/")
    return cleaned


class ExecutionRejected(ValueError):
    pass


def normalize_asset_class(value: Any) -> str:
    normalized = str(value or "stock").strip().lower()
    if normalized in {"stock", "stocks", "equity", "equities"}:
        return "stock"
    if normalized in {"option", "options"}:
        return "option"
    if normalized in {"crypto", "cryptocurrency"}:
        return "crypto"
    raise ExecutionRejected(f"Unsupported asset_class: {value}")


def normalize_alpaca_stock_time_in_force(value: Any) -> str:
    normalized = str(value or "day").strip().lower()
    if normalized in {"gfd", "day"}:
        return "day"
    return normalized


def require_whole_contract_qty(value: Any) -> str:
    try:
        qty = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ExecutionRejected("Options qty must be a whole positive number.") from exc
    if qty <= 0 or qty != qty.to_integral_value():
        raise ExecutionRejected("Options qty must be a whole positive number; fractional contracts are rejected.")
    return str(int(qty))


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


def trim_decimal(value: float, places: int = 9) -> str:
    text = f"{value:.{places}f}".rstrip("0").rstrip(".")
    return text or "0"


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


def capability_state(required: set[str], available: set[str]) -> dict[str, Any]:
    missing = sorted(required - available)
    return {
        "ready": not missing,
        "required": sorted(required),
        "missing": missing,
    }


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


def sanitized_order_args(args: dict[str, Any]) -> dict[str, Any]:
    return {
        key: ("***" if key in {"account_number", "account_id", "api_key", "secret_key"} and value else value)
        for key, value in args.items()
    }


def nested_order(payload: dict[str, Any]) -> dict[str, Any]:
    order = payload.get("order") if isinstance(payload, dict) else {}
    return order if isinstance(order, dict) else {}


def order_identifier(payload: dict[str, Any]) -> str | None:
    order = nested_order(payload)
    close_position = payload.get("close_position") if isinstance(payload, dict) else {}
    if isinstance(order, dict) and order.get("id"):
        return str(order.get("id"))
    if isinstance(close_position, dict) and close_position.get("id"):
        return str(close_position.get("id"))
    return None


def order_status(payload: dict[str, Any]) -> str | None:
    order = nested_order(payload)
    close_position = payload.get("close_position") if isinstance(payload, dict) else {}
    if isinstance(order, dict) and order.get("status"):
        return str(order.get("status"))
    if isinstance(close_position, dict) and close_position.get("status"):
        return str(close_position.get("status"))
    return None


class RobinhoodBroker:
    equity_read_tools = {"get_portfolio", "get_equity_positions", "get_equity_orders", "get_equity_quotes", "get_equity_tradability"}
    equity_order_tools = {"review_equity_order", "place_equity_order", "cancel_equity_order"}
    option_tools = {
        "get_option_chains",
        "get_option_instruments",
        "get_option_quotes",
        "get_option_positions",
        "get_option_orders",
        "review_option_order",
        "place_option_order",
        "cancel_option_order",
    }
    crypto_tools = {
        "get_crypto_positions",
        "get_crypto_quotes",
        "get_crypto_orders",
        "review_crypto_order",
        "place_crypto_order",
        "cancel_crypto_order",
    }

    def __init__(self, config: BridgeConfig):
        self.config = config
        self.client = Client(config.mcp_url, auth="oauth", timeout=config.auth_timeout_seconds)
        self.tools: set[str] = set()

    async def __aenter__(self) -> "RobinhoodBroker":
        await self.client.__aenter__()
        tools = await self.client.list_tools()
        self.tools = {str(getattr(tool, "name", "")) for tool in tools}
        required = set(self.equity_read_tools)
        if self.config.live:
            required |= self.equity_order_tools
        missing = sorted(required - self.tools)
        if missing:
            raise RuntimeError(f"Robinhood MCP missing required tools for this bridge mode: {', '.join(missing)}")
        append_log({"event": "robinhood_capability_report", "capabilities": self.capabilities()})
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

    async def place_order(self, args: dict[str, Any]) -> dict[str, Any]:
        asset_class = normalize_asset_class(args.get("asset_class"))
        if asset_class == "option":
            return await self.place_option_order(args)
        if asset_class == "crypto":
            return await self.place_crypto_order(args)
        return await self.call("place_equity_order", args)

    def capabilities(self) -> dict[str, Any]:
        options = capability_state(self.option_tools, self.tools)
        crypto = capability_state(self.crypto_tools, self.tools)
        return {
            "broker": "robinhood",
            "equity_read": capability_state(self.equity_read_tools, self.tools),
            "equity_order": capability_state(self.equity_order_tools, self.tools),
            "options": options,
            "crypto": crypto,
            "options_status": "READY" if options["ready"] else "ROLLING_OUT_OR_NOT_EXPOSED",
            "crypto_status": "READY" if crypto["ready"] else "NOT_EXPOSED_BY_CURRENT_MCP",
        }

    async def review_order(self, args: dict[str, Any]) -> dict[str, Any]:
        asset_class = normalize_asset_class(args.get("asset_class"))
        if asset_class == "option":
            return await self.review_option_order(args)
        if asset_class == "crypto":
            return await self.review_crypto_order(args)
        return await self.call("review_equity_order", args)

    async def review_option_order(self, args: dict[str, Any]) -> dict[str, Any]:
        if "review_option_order" not in self.tools:
            raise ExecutionRejected("Robinhood options execution is not exposed in this MCP session.")
        return await self.call("review_option_order", args)

    async def place_option_order(self, args: dict[str, Any]) -> dict[str, Any]:
        if "place_option_order" not in self.tools:
            raise ExecutionRejected("Robinhood options placement is not exposed in this MCP session.")
        return await self.call("place_option_order", args)

    async def review_crypto_order(self, args: dict[str, Any]) -> dict[str, Any]:
        if "review_crypto_order" not in self.tools:
            raise ExecutionRejected("Robinhood crypto execution is not exposed in this MCP session.")
        return await self.call("review_crypto_order", args)

    async def place_crypto_order(self, args: dict[str, Any]) -> dict[str, Any]:
        if "place_crypto_order" not in self.tools:
            raise ExecutionRejected("Robinhood crypto placement is not exposed in this MCP session.")
        return await self.call("place_crypto_order", args)


class AlpacaBroker:
    def __init__(self, config: BridgeConfig):
        self.config = config
        self.base_url = normalize_trading_base_url(config.alpaca_base_url)
        self.data_url = config.alpaca_data_url.rstrip("/")
        self.headers = {
            "APCA-API-KEY-ID": config.alpaca_api_key_id,
            "APCA-API-SECRET-KEY": config.alpaca_api_secret_key,
        }

    async def __aenter__(self) -> "AlpacaBroker":
        if not self.config.alpaca_api_key_id or not self.config.alpaca_api_secret_key:
            raise RuntimeError("Alpaca credentials missing. Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY.")
        account = await self.portfolio()
        if account.get("trading_blocked"):
            raise RuntimeError("Alpaca account is trading_blocked.")
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    def _trading(self, path: str, method: str = "GET", payload: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any] | list[Any]:
        return request_json_url(f"{self.base_url}{path}", method=method, payload=payload, headers=self.headers, timeout=timeout)

    def _data(self, path: str, timeout: int = 30) -> dict[str, Any]:
        return request_json_url(f"{self.data_url}{path}", headers=self.headers, timeout=timeout)

    async def portfolio(self) -> dict[str, Any]:
        account = self._trading("/v2/account")
        return {
            **account,
            "total_value": account.get("portfolio_value") or account.get("equity") or "0",
            "buying_power": {"buying_power": account.get("buying_power") or "0"},
        }

    async def account(self) -> dict[str, Any]:
        account = self._trading("/v2/account")
        return account if isinstance(account, dict) else {}

    async def positions(self) -> list[dict[str, Any]]:
        rows = self._trading("/v2/positions")
        return [
            {
                **row,
                "symbol": row.get("symbol"),
                "quantity": row.get("qty") or row.get("quantity") or "0",
                "shares_available_for_sells": row.get("qty_available") or row.get("shares_available_for_sells") or row.get("qty") or row.get("quantity") or "0",
                "average_buy_price": row.get("avg_entry_price"),
            }
            for row in (rows if isinstance(rows, list) else [])
        ]

    async def orders_today(self) -> list[dict[str, Any]]:
        start_utc = datetime.now(UTC).strftime("%Y-%m-%dT05:00:00Z")
        query = urlencode({"status": "all", "after": start_utc, "limit": 100, "nested": "false"})
        rows = self._trading(f"/v2/orders?{query}")
        return rows if isinstance(rows, list) else []

    async def quotes(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        clean_symbols = [symbol.upper() for symbol in symbols[:50] if symbol]
        if not clean_symbols:
            return {}
        query = urlencode({"symbols": ",".join(clean_symbols), "feed": "iex"})
        payload = self._data(f"/v2/stocks/quotes/latest?{query}", timeout=30)
        quotes = payload.get("quotes") or {}
        normalized: dict[str, dict[str, Any]] = {}
        for symbol, quote in quotes.items():
            bid = as_float(quote.get("bp"))
            ask = as_float(quote.get("ap"))
            last = round((bid + ask) / 2, 4) if bid > 0 and ask > 0 else ask or bid
            normalized[str(symbol).upper()] = {
                "symbol": str(symbol).upper(),
                "bid_price": bid,
                "ask_price": ask,
                "last_trade_price": last,
                "venue_bid_time": quote.get("t"),
                "venue_ask_time": quote.get("t"),
            }
        return normalized

    async def tradability(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = {}
        for symbol in [symbol.upper() for symbol in symbols[:10] if symbol]:
            asset = self._trading(f"/v2/assets/{symbol}")
            fractionable = bool(asset.get("fractionable"))
            rows[symbol] = {
                **asset,
                "symbol": symbol,
                "tradeable": bool(asset.get("tradable")),
                "state": "active" if asset.get("status") == "active" else asset.get("status"),
                "fractional_tradability": "tradable" if fractionable else "not_tradable",
            }
        return rows

    async def review_order(self, args: dict[str, Any]) -> dict[str, Any]:
        return await self.route_order(args, submit=False)

    async def place_order(self, args: dict[str, Any]) -> dict[str, Any]:
        return await self.route_order(args, submit=True)

    async def close_position(self, symbol: str, qty: float | None = None) -> dict[str, Any]:
        clean_symbol = str(symbol or "").upper().strip()
        if not clean_symbol:
            raise ExecutionRejected("Close position requires a symbol.")
        query = f"?{urlencode({'qty': trim_decimal(qty)})}" if qty is not None and qty > 0 else ""
        result = self._trading(f"/v2/positions/{clean_symbol}{query}", method="DELETE", timeout=30)
        return {"broker": "alpaca", "asset_class": "stock", "close_position": result, "symbol": clean_symbol, "qty": qty}

    async def route_order(self, args: dict[str, Any], submit: bool) -> dict[str, Any]:
        asset_class = normalize_asset_class(args.get("asset_class"))
        if asset_class == "option":
            return await self.options_executor(args, submit=submit)
        if asset_class == "crypto":
            return await self.crypto_executor(args, submit=submit)
        return await self.stock_executor(args, submit=submit)

    async def stock_executor(self, args: dict[str, Any], submit: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "symbol": args["symbol"],
            "side": args["side"],
            "type": args["type"],
            "time_in_force": normalize_alpaca_stock_time_in_force(args.get("time_in_force", "day")),
        }
        if args.get("dollar_amount"):
            payload["notional"] = str(args["dollar_amount"])
        if args.get("quantity"):
            payload["qty"] = str(args["quantity"])
        if args.get("limit_price"):
            payload["limit_price"] = str(args["limit_price"])
        if args.get("market_hours") in {"extended_hours", "all_day_hours"}:
            payload["extended_hours"] = True
        if not submit:
            return {"broker": "alpaca", "asset_class": "stock", "order_checks": {}, "normalized_intent": payload}
        order = self._trading("/v2/orders", method="POST", payload=payload, timeout=30)
        return {"broker": "alpaca", "asset_class": "stock", "order": order, "normalized_intent": payload}

    async def crypto_executor(self, args: dict[str, Any], submit: bool) -> dict[str, Any]:
        account = await self.account()
        crypto_status = str(account.get("crypto_status") or "").upper()
        if not self.config.enable_crypto_execution:
            raise ExecutionRejected("Crypto execution is disabled. Set ENABLE_CRYPTO_EXECUTION=true to allow crypto routing.")
        if crypto_status != "ACTIVE":
            raise ExecutionRejected(f"Crypto execution rejected because Alpaca crypto_status is {crypto_status or 'UNKNOWN'}.")
        if args.get("dollar_amount") and (args.get("quantity") or args.get("qty")):
            raise ExecutionRejected("Crypto orders must use either notional/dollar_amount or qty, not both.")
        payload: dict[str, Any] = {
            "symbol": args["symbol"],
            "side": args["side"],
            "type": args.get("type", "market"),
            "time_in_force": args.get("time_in_force", "gtc"),
        }
        if payload["side"] not in {"buy", "sell"}:
            raise ExecutionRejected("Crypto executor requires side=buy or side=sell.")
        if payload["type"] not in {"market", "limit", "stop_limit"}:
            raise ExecutionRejected("Crypto executor allows only market, limit, and stop_limit orders.")
        if payload["type"] == "market" and not self.config.allow_market_crypto:
            raise ExecutionRejected("Market crypto orders are disabled. Use a limit order or set ALLOW_MARKET_CRYPTO=true.")
        if payload["time_in_force"] not in {"gtc", "ioc"}:
            raise ExecutionRejected("Crypto time_in_force must be gtc or ioc.")
        if args.get("dollar_amount") or args.get("notional"):
            payload["notional"] = str(args.get("dollar_amount") or args.get("notional"))
        if args.get("quantity") or args.get("qty"):
            payload["qty"] = str(args.get("quantity") or args.get("qty"))
        if not payload.get("notional") and not payload.get("qty"):
            raise ExecutionRejected("Crypto executor requires notional/dollar_amount or qty.")
        if args.get("limit_price"):
            payload["limit_price"] = str(args["limit_price"])
        if payload["type"] in {"limit", "stop_limit"} and not payload.get("limit_price"):
            raise ExecutionRejected("Crypto limit and stop_limit orders require limit_price.")
        if not submit:
            return {"broker": "alpaca", "asset_class": "crypto", "order_checks": {}, "normalized_intent": payload}
        order = self._trading("/v2/orders", method="POST", payload=payload, timeout=30)
        return {"broker": "alpaca", "asset_class": "crypto", "order": order, "normalized_intent": payload}

    async def ensure_options_capable(self, position_intent: str | None) -> dict[str, Any]:
        account = await self.account()
        level = max(int(as_float(account.get("options_trading_level"))), int(as_float(account.get("options_approved_level"))))
        if level < 1:
            raise ExecutionRejected("Options execution rejected: Alpaca options trading is not enabled.")
        if position_intent == "buy_to_open" and level < 2:
            raise ExecutionRejected("Options execution rejected: buying calls/puts requires Alpaca options level 2 or higher.")
        return {"options_level": level, "account_status": account.get("status"), "trading_blocked": account.get("trading_blocked")}

    async def option_contracts(
        self,
        underlying: str,
        expiration: str | None = None,
        option_type: str | None = None,
        strike: str | float | None = None,
    ) -> list[dict[str, Any]]:
        query_values: dict[str, Any] = {"underlying_symbols": underlying.upper(), "status": "active", "limit": 10000}
        if expiration:
            query_values["expiration_date"] = expiration
        if option_type:
            query_values["type"] = str(option_type).lower()
        if strike is not None:
            query_values["strike_price_gte"] = str(strike)
            query_values["strike_price_lte"] = str(strike)
        contracts: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            values = dict(query_values)
            if page_token:
                values["page_token"] = page_token
            payload = self._trading(f"/v2/options/contracts?{urlencode(values)}")
            if not isinstance(payload, dict):
                break
            contracts.extend(list(payload.get("option_contracts") or []))
            page_token = payload.get("next_page_token")
            if not page_token:
                break
        return [
            row
            for row in contracts
            if str(row.get("status") or "").lower() == "active" and bool(row.get("tradable"))
        ]

    async def lookup_option_contract(self, underlying: str, expiration: str, option_type: str, strike: str | float) -> str:
        target_strike = Decimal(str(strike))
        contracts = await self.option_contracts(underlying, expiration=expiration, option_type=option_type, strike=strike)
        for contract in contracts:
            try:
                contract_strike = Decimal(str(contract.get("strike_price")))
            except (InvalidOperation, ValueError):
                continue
            if (
                str(contract.get("underlying_symbol") or "").upper() == underlying.upper()
                and str(contract.get("expiration_date") or "") == expiration
                and str(contract.get("type") or "").lower() == option_type.lower()
                and contract_strike == target_strike
            ):
                symbol = str(contract.get("symbol") or "")
                if symbol:
                    return symbol
        raise ExecutionRejected(f"No active tradable {underlying.upper()} {expiration} {option_type.lower()} {strike} option contract found.")

    async def normalize_option_order(self, args: dict[str, Any]) -> dict[str, Any]:
        if args.get("dollar_amount") or args.get("notional"):
            raise ExecutionRejected("Options orders reject notional/dollar_amount; use whole-number qty.")
        symbol = str(args.get("symbol") or args.get("contract_symbol") or "").upper()
        if not symbol and args.get("underlying") and args.get("expiration") and args.get("option_type") and args.get("strike"):
            symbol = await self.lookup_option_contract(
                str(args["underlying"]),
                str(args["expiration"]),
                str(args["option_type"]),
                str(args["strike"]),
            )
        if not symbol:
            raise ExecutionRejected("Options executor requires an OCC option contract symbol.")
        qty = require_whole_contract_qty(args.get("quantity") or args.get("qty"))
        position_intent = str(args.get("position_intent") or "").lower() or None
        if position_intent and position_intent not in {"buy_to_open", "sell_to_close"}:
            raise ExecutionRejected("Options executor initially allows only buy_to_open and sell_to_close intents.")
        side = str(args.get("side") or "").lower()
        if not side and position_intent:
            side = "buy" if position_intent == "buy_to_open" else "sell"
        if side not in {"buy", "sell"}:
            raise ExecutionRejected("Options executor requires side=buy or side=sell.")
        order_type = str(args.get("type") or "limit").lower()
        if order_type not in {"market", "limit"}:
            raise ExecutionRejected("Options executor initially allows only market and limit orders.")
        if order_type == "market" and not self.config.allow_market_options:
            raise ExecutionRejected("Market options orders are disabled. Set ALLOW_MARKET_OPTIONS=true to allow them.")
        limit_price = args.get("limit_price")
        if order_type == "limit" and not limit_price:
            raise ExecutionRejected("Options limit orders require limit_price.")
        payload: dict[str, Any] = {
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "type": order_type,
            "time_in_force": "day",
            "extended_hours": False,
            "order_class": "simple",
        }
        if position_intent:
            payload["position_intent"] = position_intent
        if limit_price:
            price = Decimal(str(limit_price))
            if price <= 0:
                raise ExecutionRejected("Options limit_price must be positive.")
            payload["limit_price"] = str(limit_price)
            estimated_cost = float(price * Decimal(qty) * Decimal("100"))
            if self.config.max_option_contract_cost > 0 and estimated_cost > self.config.max_option_contract_cost:
                raise ExecutionRejected(f"Options order estimated cost ${estimated_cost:.2f} exceeds max contract cost ${self.config.max_option_contract_cost:.2f}.")
            if self.config.max_option_account_risk > 0 and estimated_cost > self.config.max_option_account_risk:
                raise ExecutionRejected(f"Options order estimated risk ${estimated_cost:.2f} exceeds max account-risk cap ${self.config.max_option_account_risk:.2f}.")
        return payload

    async def options_executor(self, args: dict[str, Any], submit: bool) -> dict[str, Any]:
        payload = await self.normalize_option_order(args)
        capability = await self.ensure_options_capable(payload.get("position_intent"))
        append_log({"event": "alpaca_option_intent_normalized", "normalized_intent": payload, "capability": capability, "submit": submit})
        if not submit:
            return {"broker": "alpaca", "asset_class": "option", "order_checks": {}, "normalized_intent": payload, "capability": capability}
        order = self._trading("/v2/orders", method="POST", payload=payload, timeout=30)
        append_log({"event": "alpaca_option_order_response", "normalized_intent": payload, "response": order})
        return {"broker": "alpaca", "asset_class": "option", "order": order, "normalized_intent": payload, "capability": capability}


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


def strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def optional_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def candidate_evidence_profile(row: dict[str, Any]) -> dict[str, Any]:
    signals = row.get("key_signals") if isinstance(row.get("key_signals"), dict) else {}
    scorecard = signals.get("evidence_scorecard") if isinstance(signals.get("evidence_scorecard"), dict) else {}
    relative_strength = signals.get("relative_strength") if isinstance(signals.get("relative_strength"), dict) else {}
    packet = row.get("evidence_packet") if isinstance(row.get("evidence_packet"), dict) else {}
    confidence = packet.get("data_confidence") if isinstance(packet.get("data_confidence"), dict) else {}
    return {
        "evidence_score": optional_float(scorecard.get("preview_final_score")),
        "data_confidence_score": optional_float(confidence.get("score")),
        "data_confidence_status": str(confidence.get("status") or "UNKNOWN"),
        "data_flags": strings(packet.get("data_flags")),
        "relative_strength_label": str(relative_strength.get("label") or "unknown"),
        "relative_strength_excess_trend_pct": optional_float(relative_strength.get("excess_trend_pct")),
        "relative_strength_excess_recent_trend_pct": optional_float(relative_strength.get("excess_recent_trend_pct")),
    }


def candidate_bridge_rank_score(row: dict[str, Any], profile: dict[str, Any]) -> float:
    stock_score = as_float(row.get("stock_score"))
    relative_volume = as_float(row.get("relative_volume"))
    score = stock_score + min(6.0, relative_volume * 1.5)

    evidence_score = profile.get("evidence_score")
    if evidence_score is not None:
        score += max(-6.0, min(6.0, (float(evidence_score) - 50.0) * 0.12))

    confidence_score = profile.get("data_confidence_score")
    if confidence_score is not None:
        score += max(-8.0, min(4.0, (float(confidence_score) - 70.0) * 0.08))

    label = str(profile.get("relative_strength_label") or "").lower()
    if "leading" in label:
        score += 3.0
    elif "lagging" in label:
        score -= 4.0
    elif "mixed" in label:
        score -= 1.0

    flags = set(profile.get("data_flags") or [])
    if "quote_derived_from_candles" in flags:
        score -= 1.5
    if "relative_volume_below_preferred_floor" in flags:
        score -= 2.0
    if "relative_volume_unavailable" in flags:
        score -= 3.0
    if "catalyst_context_missing" in flags:
        score -= 0.5
    if "sector_relative_strength_missing" in flags:
        score -= 0.5
    if "l2_order_flow_missing" in flags:
        score -= 0.5
    return round(score, 4)


def evaluate_long_candidate(
    row: dict[str, Any],
    quotes: dict[str, dict[str, Any]],
    tradability: dict[str, dict[str, Any]],
    held_symbols: set[str],
    config: BridgeConfig,
) -> dict[str, Any]:
    symbol = str(row.get("ticker") or "").upper()
    profile = candidate_evidence_profile(row)
    rejection_reasons: list[str] = []
    spread_bps: float | None = None

    if not symbol:
        rejection_reasons.append("missing_symbol")
    if symbol in held_symbols:
        rejection_reasons.append("already_held")
    if str(row.get("stock_direction") or "").lower() != "long":
        rejection_reasons.append("not_long")
    if str(row.get("stock_setup_quality") or "") != "VALID_CANDIDATE":
        rejection_reasons.append("not_valid_candidate")
    if as_float(row.get("stock_score")) < config.min_score:
        rejection_reasons.append("score_below_min")
    if as_float(row.get("relative_volume")) < config.min_relative_volume:
        rejection_reasons.append("relative_volume_below_min")
    if str(row.get("vwap_state") or "").lower() != "above":
        rejection_reasons.append("not_above_vwap")

    flags = set(profile.get("data_flags") or [])
    if {"quote_stale", "candles_stale"}.intersection(flags):
        rejection_reasons.append("stale_market_data")
    confidence_status = str(profile.get("data_confidence_status") or "").upper()
    confidence_score = profile.get("data_confidence_score")
    if confidence_status == "LOW" or (confidence_score is not None and float(confidence_score) < 55.0):
        rejection_reasons.append("low_data_confidence")

    trade = tradability.get(symbol) or {}
    if not trade.get("tradeable") or trade.get("state") != "active":
        rejection_reasons.append("not_tradeable")

    quote = quotes.get(symbol) or {}
    bid = as_float(quote.get("bid_price"))
    ask = as_float(quote.get("ask_price"))
    last = as_float(quote.get("last_trade_price"))
    ref = ask or last
    if ref <= 0 or bid <= 0 or ask <= 0:
        rejection_reasons.append("invalid_quote")
    else:
        spread_bps = ((ask - bid) / ref) * 10000
        if spread_bps > config.max_spread_bps:
            rejection_reasons.append("spread_too_wide")

    rank_score = candidate_bridge_rank_score(row, profile)
    return {
        "symbol": symbol,
        "passed": not rejection_reasons,
        "rejection_reasons": rejection_reasons,
        "rank_score": rank_score,
        "stock_score": as_float(row.get("stock_score")),
        "relative_volume": as_float(row.get("relative_volume")),
        "spread_bps": round(spread_bps, 2) if spread_bps is not None else None,
        "evidence_profile": profile,
        "scan": row,
        "quote": quote,
        "tradability": trade,
    }


def rank_long_candidates(
    candidates: list[dict[str, Any]],
    quotes: dict[str, dict[str, Any]],
    tradability: dict[str, dict[str, Any]],
    held_symbols: set[str],
    config: BridgeConfig,
) -> list[dict[str, Any]]:
    diagnostics = [
        evaluate_long_candidate(row, quotes, tradability, held_symbols, config)
        for row in candidates
    ]
    return sorted(
        diagnostics,
        key=lambda item: (
            item["passed"],
            item["rank_score"],
            item["stock_score"],
            item["relative_volume"],
            item["symbol"],
        ),
        reverse=True,
    )


def candidate_ranking_log_payload(ranked: list[dict[str, Any]], limit: int = 8) -> dict[str, Any]:
    rows = []
    for item in ranked[: max(1, limit)]:
        profile = item.get("evidence_profile") or {}
        rows.append(
            {
                "symbol": item.get("symbol"),
                "passed": item.get("passed"),
                "rejection_reasons": item.get("rejection_reasons"),
                "rank_score": item.get("rank_score"),
                "stock_score": item.get("stock_score"),
                "relative_volume": item.get("relative_volume"),
                "spread_bps": item.get("spread_bps"),
                "evidence_score": profile.get("evidence_score"),
                "data_confidence_score": profile.get("data_confidence_score"),
                "data_confidence_status": profile.get("data_confidence_status"),
                "relative_strength_label": profile.get("relative_strength_label"),
                "data_flags": profile.get("data_flags"),
            }
        )
    return {
        "event": "candidate_ranking_summary",
        "candidate_count": len(ranked),
        "passed_count": sum(1 for item in ranked if item.get("passed")),
        "top_candidates": rows,
    }


def select_long_candidate(
    candidates: list[dict[str, Any]],
    quotes: dict[str, dict[str, Any]],
    tradability: dict[str, dict[str, Any]],
    held_symbols: set[str],
    config: BridgeConfig,
) -> dict[str, Any] | None:
    ranked = rank_long_candidates(candidates, quotes, tradability, held_symbols, config)
    append_log(candidate_ranking_log_payload(ranked))
    for item in ranked:
        if not item.get("passed"):
            continue
        return {
            "scan": item["scan"],
            "quote": item["quote"],
            "tradability": item["tradability"],
            "spread_bps": item["spread_bps"],
            "bridge_rank_score": item["rank_score"],
            "bridge_evidence_profile": item["evidence_profile"],
        }
    return None


def position_value(position: dict[str, Any], quote: dict[str, Any]) -> float:
    qty = as_float(position.get("quantity"))
    last = as_float(quote.get("last_trade_price"))
    return qty * last


async def place_exit_order(broker: RobinhoodBroker, symbol: str, qty: float, args: dict[str, Any]) -> dict[str, Any]:
    try:
        return await broker.place_order({**args, "ref_id": str(uuid.uuid4())})
    except Exception as exc:  # noqa: BLE001 - fallback handles broker-specific close paths
        if hasattr(broker, "close_position"):
            append_log(
                {
                    "event": "exit_place_order_failed_trying_close_position",
                    "symbol": symbol,
                    "order_args": sanitized_order_args(args),
                    "error": repr(exc),
                }
            )
            return await broker.close_position(symbol, qty)  # type: ignore[attr-defined]
        raise


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
        try:
            review = await broker.review_order(args)
        except Exception as exc:  # noqa: BLE001 - keep managing other positions after one broker refusal
            append_log({"event": "exit_review_failed", "symbol": symbol, "reason": exit_reason, "pnl_pct": pnl_pct, "error": repr(exc)})
            continue
        append_log({"event": "exit_review", "symbol": symbol, "reason": exit_reason, "pnl_pct": pnl_pct, "review": review})
        if not config.live:
            continue
        try:
            placed = await place_exit_order(broker, symbol, qty, args)
        except Exception as exc:  # noqa: BLE001 - log and retry on a later cycle if the exit is still valid
            append_log({"event": "exit_place_failed", "symbol": symbol, "reason": exit_reason, "pnl_pct": pnl_pct, "order_args": sanitized_order_args(args), "error": repr(exc)})
            continue
        append_log({"event": "exit_placed", "symbol": symbol, "reason": exit_reason, "order": placed})
        if not is_real_cash_execution(config):
            try:
                record_paper_lifecycle_exit(
                    broker=config.broker,
                    scope=state_scope(config),
                    symbol=symbol,
                    order_id=order_identifier(placed),
                    order_status=order_status(placed) or "submitted",
                    quantity=qty,
                    entry_reference_price=avg,
                    exit_reference_price=last,
                    exit_reason=exit_reason,
                )
            except Exception as exc:  # noqa: BLE001 - lifecycle evidence must not kill risk management
                append_log({"event": "paper_lifecycle_exit_log_failed", "symbol": symbol, "error": repr(exc)})
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


def is_real_cash_execution(config: BridgeConfig) -> bool:
    if config.broker == "alpaca" and alpaca_endpoint_environment(config.alpaca_base_url) == "paper":
        return False
    return bool(config.live)


def log_broker_action(config: BridgeConfig, payload: dict[str, Any]) -> None:
    try:
        payload = {"is_options_order": False, "is_real_cash": is_real_cash_execution(config), **payload}
        post_json_url(f"{config.base_url.rstrip('/')}/trade/manual-action", payload, timeout=30)
    except Exception as exc:  # noqa: BLE001 - logging must not kill executor
        append_log({"event": "journal_log_failed", "error": repr(exc), "payload": payload})


def state_scope(config: BridgeConfig) -> str:
    if config.broker == "alpaca":
        raw = f"{config.broker}:{normalize_trading_base_url(config.alpaca_base_url)}:{config.alpaca_api_key_id}"
    else:
        raw = f"{config.broker}:{config.account_number}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def state_for_today(state: dict[str, Any], portfolio: dict[str, Any], config: BridgeConfig) -> dict[str, Any]:
    key = today_key()
    scope = state_scope(config)
    if state.get("date") != key or state.get("broker") != config.broker or state.get("scope") != scope:
        state.clear()
        state.update(
            {
                "date": key,
                "broker": config.broker,
                "scope": scope,
                "day_start_value": as_float(portfolio.get("total_value")),
                "trade_count": 0,
                "halted": False,
                "last_order_ids": [],
            }
        )
    elif as_float(state.get("day_start_value")) <= 0 and as_float(portfolio.get("total_value")) > 0:
        state["day_start_value"] = as_float(portfolio.get("total_value"))
        state["halted"] = False
    return state


async def run_cycle(broker: RobinhoodBroker, config: BridgeConfig, state: dict[str, Any]) -> None:
    portfolio = await broker.portfolio()
    state_for_today(state, portfolio, config)
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
    session = current_equity_session()
    if session == "closed":
        append_log({"event": "entry_skipped_market_closed", "session": session, "next_action": "Position management checked; new entries wait for the next equity session."})
        save_state(state)
        return
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
    if not is_real_cash_execution(config):
        try:
            review_quote = review.get("quote_data") if isinstance(review, dict) and isinstance(review.get("quote_data"), dict) else {}
            ref_price = (
                as_float(order.get("filled_avg_price"))
                or as_float(order.get("average_price"))
                or as_float(order.get("price"))
                or as_float(review_quote.get("ask_price"))
            )
            quote = selected.get("quote") or {}
            if ref_price <= 0:
                ref_price = as_float(quote.get("ask_price")) or as_float(quote.get("last_trade_price"))
            quantity = as_float(order.get("filled_qty") or order.get("qty") or order.get("cumulative_quantity"))
            if quantity <= 0 and ref_price > 0:
                quantity = notional / ref_price
            scan = selected.get("scan") or {}
            record_paper_lifecycle_entry(
                broker=config.broker,
                scope=state_scope(config),
                symbol=symbol,
                order_id=order_identifier(placed),
                order_status=order_status(placed) or "submitted",
                notional=notional,
                quantity=quantity if quantity > 0 else None,
                reference_price=ref_price if ref_price > 0 else None,
                setup={
                    "stock_score": as_float(scan.get("stock_score")),
                    "relative_volume": as_float(scan.get("relative_volume")),
                    "vwap_state": scan.get("vwap_state"),
                    "stock_setup_quality": scan.get("stock_setup_quality"),
                    "bridge_rank_score": selected.get("bridge_rank_score"),
                    "bridge_evidence_profile": selected.get("bridge_evidence_profile"),
                    "intent_hash": intent.get("intent_hash"),
                },
                risk={
                    "max_order_notional": config.max_order_notional,
                    "max_daily_loss": config.max_daily_loss,
                    "stop_loss_pct": config.stop_loss_pct,
                    "take_profit_pct": config.take_profit_pct,
                    "max_open_positions": config.max_open_positions,
                    "max_trades_per_day": config.max_trades_per_day,
                    "spread_bps": selected.get("spread_bps"),
                },
            )
        except Exception as exc:  # noqa: BLE001 - lifecycle evidence must not kill order handling
            append_log({"event": "paper_lifecycle_entry_log_failed", "symbol": symbol, "error": repr(exc)})
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
    parser.add_argument("--broker", choices=["robinhood", "alpaca"], default=os.getenv("STOCK_BRIDGE_BROKER", "robinhood").strip().lower())
    parser.add_argument("--base-url", default=os.getenv("SCREENER_BASE_URL", "https://living-screener-mcp.onrender.com"))
    parser.add_argument("--mcp-url", default=os.getenv("ROBINHOOD_MCP_URL", "https://agent.robinhood.com/mcp/trading"))
    parser.add_argument("--account-number", default=os.getenv("ROBINHOOD_ACCOUNT_NUMBER", "628006199"))
    parser.add_argument("--alpaca-base-url", default=os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"))
    parser.add_argument("--alpaca-data-url", default=os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets"))
    parser.add_argument("--alpaca-api-key-id", default=os.getenv("ALPACA_API_KEY_ID", ""))
    parser.add_argument("--alpaca-api-secret-key", default=os.getenv("ALPACA_API_SECRET_KEY", ""))
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
    parser.add_argument("--max-daily-loss", type=float, default=float(os.getenv("STOCK_BRIDGE_MAX_DAILY_LOSS", "5")))
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
    parser.add_argument("--enable-crypto-execution", action="store_true", default=as_bool(os.getenv("ENABLE_CRYPTO_EXECUTION", "false")))
    parser.add_argument("--allow-market-options", action="store_true", default=as_bool(os.getenv("ALLOW_MARKET_OPTIONS", "false")))
    parser.add_argument("--allow-market-crypto", action="store_true", default=as_bool(os.getenv("ALLOW_MARKET_CRYPTO", "false")))
    parser.add_argument("--max-option-contract-cost", type=float, default=float(os.getenv("MAX_OPTION_CONTRACT_COST", os.getenv("STOCK_BRIDGE_MAX_ORDER_NOTIONAL", "10"))))
    parser.add_argument("--max-option-account-risk", type=float, default=float(os.getenv("MAX_OPTION_ACCOUNT_RISK", os.getenv("STOCK_BRIDGE_MAX_DAILY_LOSS", "20"))))
    args = parser.parse_args(argv)
    raw = vars(args)
    raw["allowed_broker_alert_types"] = tuple(
        item.strip().upper()
        for item in str(raw["allowed_broker_alert_types"]).split(",")
        if item.strip()
    )
    config = BridgeConfig(**raw)
    enforce_live_readiness_gate(config.live, config.broker, config.alpaca_base_url)
    enforce_live_config_caps(config)
    if (
        config.live
        and os.getenv("STOCK_BRIDGE_LIVE_AUTH") != LIVE_AUTH_VALUE
        and not is_alpaca_paper_submission(config.live, config.broker, config.alpaca_base_url)
    ):
        raise SystemExit(
            "Live mode refused. Set STOCK_BRIDGE_LIVE_AUTH=ENABLE_AGENTIC_STOCK_BRIDGE "
            "to acknowledge real-money autonomous trading risk."
        )
    return config


async def async_main(argv: list[str]) -> int:
    config = parse_args(argv)
    safe_config = {
        **asdict(config),
        "account_number": "***",
        "alpaca_api_key_id": "***" if config.alpaca_api_key_id else "",
        "alpaca_api_secret_key": "***" if config.alpaca_api_secret_key else "",
    }
    append_log({"event": "bridge_start", "config": safe_config})
    print(f"Living Screener stock bridge loop | broker={config.broker} | live={config.live} | account={config.account_number} | base={config.base_url}")
    print(f"Logs: {LOG_PATH}")
    print(f"State: {STATE_PATH}")
    if config.broker == "robinhood":
        print("If OAuth opens a Robinhood URL, approve it in the browser to connect the local executor.")
    state = load_state()
    consecutive_errors = 0
    broker_cls = AlpacaBroker if config.broker == "alpaca" else RobinhoodBroker
    async with broker_cls(config) as broker:
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
