from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from app.config import Settings
from app.storage.repositories import EventRepository


class OptionsService:
    def __init__(self, settings: Settings, events: EventRepository):
        self.settings = settings
        self.events = events

    def validate_chain(self, ticker: str, direction: str = "call", max_contract_price: float | None = None) -> dict:
        symbol = ticker.upper()
        side = "puts" if direction.lower() in {"put", "puts", "short"} else "calls"
        try:
            contracts = self._load_yfinance_chain(symbol, side)
        except Exception as exc:
            return self._log_no_trade(symbol, [f"Options-chain provider failed safely: {type(exc).__name__}."], side)

        if not contracts:
            return self._log_no_trade(symbol, ["Options-chain data missing or unavailable."], side)

        candidates = [self._score_contract(contract, max_contract_price) for contract in contracts]
        accepted = [contract for contract in candidates if contract["quality_status"] == "ACCEPTABLE"]
        rejected = [contract for contract in candidates if contract["quality_status"] != "ACCEPTABLE"]
        best_rejected = sorted(rejected, key=self._rejected_sort_key)[: self.settings.max_option_contracts_returned]
        result = {
            "ticker": symbol,
            "direction": "put" if side == "puts" else "call",
            "status": "OPTIONS_CHAIN_ACCEPTABLE" if accepted else "NO_TRADE_PLAN",
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "chain_provider": "yfinance",
            "quality_gate": self._quality_gate_summary(candidates),
            "accepted_contracts": accepted[: self.settings.max_option_contracts_returned],
            "rejected_sample": rejected[: self.settings.max_option_contracts_returned],
            "best_rejected_contracts": best_rejected,
            "notes": "Review-only options quality check. This MCP cannot place orders.",
        }
        return self.events.log("options_chain_validation", result)

    def validate_broker_snapshot(self, snapshot: dict[str, Any], max_contract_price: float | None = None) -> dict:
        symbol = str(snapshot.get("ticker") or snapshot.get("underlying") or "").upper()
        direction = str(snapshot.get("direction") or snapshot.get("type") or "call").lower()
        side = "puts" if direction in {"put", "puts", "short"} else "calls"
        bid = self._float(snapshot.get("bid")) or 0.0
        ask = self._float(snapshot.get("ask")) or 0.0
        last = self._float(snapshot.get("last_price", snapshot.get("last"))) or 0.0
        now = datetime.now(UTC)
        receipt_ts = self._parse_timestamp(snapshot.get("broker_snapshot_ts") or snapshot.get("snapshot_ts") or snapshot.get("quote_ts") or snapshot.get("timestamp")) or now
        quote_ts = self._parse_timestamp(snapshot.get("option_quote_ts") or snapshot.get("quote_ts") or snapshot.get("timestamp")) or receipt_ts
        quote_time_source = "provided" if any(snapshot.get(key) for key in ["option_quote_ts", "quote_ts", "timestamp"]) else "captured_at_validation"
        quote_age_seconds = round((now - quote_ts).total_seconds(), 3) if quote_ts else None
        contract_symbol = str(snapshot.get("contract_symbol") or snapshot.get("symbol") or "")
        displayed_symbol = str(snapshot.get("displayed_symbol") or contract_symbol)
        expected_contract_symbol = str(snapshot.get("expected_contract_symbol") or snapshot.get("reviewed_contract_symbol") or "")
        multiplier = self._int(snapshot.get("multiplier")) or 100
        deliverable = str(snapshot.get("deliverable") or "100 shares")
        bid_size = self._int(snapshot.get("bid_size", snapshot.get("bidSize"))) or None
        ask_size = self._int(snapshot.get("ask_size", snapshot.get("askSize"))) or None
        adjusted_raw = snapshot.get("is_adjusted", snapshot.get("adjusted_contract"))
        is_adjusted = str(adjusted_raw).strip().lower() in {"1", "true", "yes", "y", "on"} if adjusted_raw is not None else False
        event_flags = self._event_flags(snapshot, is_adjusted)
        mismatch_codes = self._snapshot_mismatch_codes(
            symbol=symbol,
            contract_symbol=contract_symbol,
            displayed_symbol=displayed_symbol,
            expected_contract_symbol=expected_contract_symbol,
            bid=bid,
            ask=ask,
            quote_age_seconds=quote_age_seconds,
            is_adjusted=is_adjusted,
            event_flags=event_flags,
        )
        contract = {
            "contract_symbol": contract_symbol,
            "ticker": symbol,
            "expiration": snapshot.get("expiration"),
            "days_to_expiration": self._int(snapshot.get("days_to_expiration", snapshot.get("dte"))) or 0,
            "strike": self._float(snapshot.get("strike")),
            "bid": bid,
            "ask": ask,
            "bid_size": bid_size,
            "ask_size": ask_size,
            "last_price": last,
            "midpoint": round((bid + ask) / 2, 4) if bid > 0 and ask > 0 else last,
            "volume": self._int(snapshot.get("volume")) or 0,
            "open_interest": self._int(snapshot.get("open_interest", snapshot.get("openInterest"))) or 0,
            "implied_volatility": self._float(snapshot.get("implied_volatility", snapshot.get("iv"))),
            "max_loss_dollars": round(ask * multiplier, 2) if ask > 0 else None,
            "break_even": None,
            "multiplier": multiplier,
            "deliverable": deliverable,
            "is_adjusted": is_adjusted,
            "event_flags": event_flags,
            "quote_age_seconds": quote_age_seconds,
            "source": str(snapshot.get("source") or "manual_broker_snapshot"),
            "displayed_symbol": displayed_symbol,
            "expected_contract_symbol": expected_contract_symbol or None,
        }
        scored = self._score_contract(contract, max_contract_price)
        missing_required = []
        if not symbol:
            missing_required.append("Ticker missing.")
        if not contract["contract_symbol"]:
            missing_required.append("Contract symbol missing.")
        if missing_required:
            scored = dict(scored)
            scored["reasons"] = missing_required + scored["reasons"]
            scored["quality_status"] = "REJECTED"
        if mismatch_codes:
            scored = dict(scored)
            scored["reasons"] = [*mismatch_codes, *scored["reasons"]]
            scored["quality_status"] = "REJECTED"
        accepted = scored["quality_status"] == "ACCEPTABLE"
        liquidity_gate = self._liquidity_gate(scored)
        option_snapshot_v2 = {
            "schema_version": "OptionSnapshotV2",
            "source": str(snapshot.get("source") or "manual_broker_snapshot"),
            "source_receipt_time_utc": receipt_ts.isoformat() if receipt_ts else now.isoformat(),
            "option_quote_time_utc": quote_ts.isoformat() if quote_ts else None,
            "quote_time_source": quote_time_source,
            "quote_age_seconds": quote_age_seconds,
            "underlying": symbol,
            "displayed_symbol": displayed_symbol,
            "contract_symbol": contract_symbol,
            "expected_contract_symbol": expected_contract_symbol or None,
            "expiration": contract.get("expiration"),
            "strike": contract.get("strike"),
            "right": "put" if side == "puts" else "call",
            "multiplier": multiplier,
            "deliverable": deliverable,
            "bid": bid,
            "ask": ask,
            "bid_size": bid_size,
            "ask_size": ask_size,
            "spread_abs": liquidity_gate["spread_abs"],
            "spread_pct_mid": liquidity_gate["spread_pct_mid"],
            "volume": contract["volume"],
            "open_interest": contract["open_interest"],
            "mark": self._float(snapshot.get("mark")) or scored.get("midpoint"),
            "is_adjusted": is_adjusted,
            "event_flags": event_flags,
            "mismatch_codes": mismatch_codes,
            "liquidity_gate_result": liquidity_gate,
        }
        result = {
            "ticker": symbol,
            "direction": "put" if side == "puts" else "call",
            "status": "OPTIONS_CHAIN_ACCEPTABLE" if accepted else "NO_TRADE_PLAN",
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "chain_provider": "broker_snapshot_manual",
            "max_contract_price_used": max_contract_price,
            "quality_gate": self._quality_gate_from_reasons(scored["reasons"]),
            "option_snapshot_v2": option_snapshot_v2,
            "mismatch_codes": mismatch_codes,
            "liquidity_gate_result": liquidity_gate,
            "accepted_contracts": [scored] if accepted else [],
            "rejected_sample": [] if accepted else [scored],
            "best_rejected_contracts": [] if accepted else [scored],
            "notes": "Manual broker-visible snapshot validation only. This MCP cannot place orders and does not store broker credentials.",
        }
        return self.events.log("broker_options_snapshot_validation", result)

    def _load_yfinance_chain(self, ticker: str, side: str) -> list[dict[str, Any]]:
        import yfinance as yf

        optionable = yf.Ticker(ticker)
        expirations = list(getattr(optionable, "options", []) or [])
        contracts: list[dict[str, Any]] = []
        today = datetime.now(UTC).date()
        for expiration in expirations:
            expiration_date = self._parse_expiration(expiration)
            if expiration_date is None:
                continue
            dte = (expiration_date - today).days
            if dte < self.settings.min_option_days_to_expiration or dte > self.settings.max_option_days_to_expiration:
                continue
            chain = optionable.option_chain(expiration)
            table = getattr(chain, side)
            for _, row in table.iterrows():
                contracts.append(self._row_to_contract(ticker, expiration, dte, row))
        return contracts

    def _row_to_contract(self, ticker: str, expiration: str, dte: int, row: Any) -> dict[str, Any]:
        bid = self._float(row.get("bid")) or 0.0
        ask = self._float(row.get("ask")) or 0.0
        last = self._float(row.get("lastPrice")) or 0.0
        midpoint = (bid + ask) / 2 if bid > 0 and ask > 0 else last
        max_loss = round(ask * 100, 2) if ask > 0 else None
        return {
            "contract_symbol": str(row.get("contractSymbol", "")),
            "ticker": ticker.upper(),
            "expiration": expiration,
            "days_to_expiration": dte,
            "strike": self._float(row.get("strike")),
            "bid": bid,
            "ask": ask,
            "last_price": last,
            "midpoint": round(midpoint, 4) if midpoint else None,
            "volume": self._int(row.get("volume")) or 0,
            "open_interest": self._int(row.get("openInterest")) or 0,
            "implied_volatility": self._float(row.get("impliedVolatility")),
            "max_loss_dollars": max_loss,
            "break_even": None,
        }

    def _score_contract(self, contract: dict[str, Any], max_contract_price: float | None) -> dict[str, Any]:
        reasons: list[str] = []
        bid = float(contract["bid"])
        ask = float(contract["ask"])
        midpoint = contract.get("midpoint") or ((bid + ask) / 2 if bid > 0 and ask > 0 else 0.0)
        spread_pct = None
        if bid <= 0 or ask <= 0 or ask < bid:
            reasons.append("Bid/ask missing or invalid.")
        elif midpoint <= 0:
            reasons.append("Midpoint missing.")
        else:
            spread_pct = (ask - bid) / midpoint
            if spread_pct > self.settings.max_option_spread_pct:
                reasons.append("Bid/ask spread too wide.")
        if contract["volume"] < self.settings.min_option_volume:
            reasons.append("Contract volume below floor.")
        if contract["open_interest"] < self.settings.min_option_open_interest:
            reasons.append("Open interest below floor.")
        if contract.get("is_adjusted"):
            reasons.append("Adjusted/non-standard contract requires separate OCC/manual review.")
        if contract.get("event_flags"):
            reasons.append("Event flag present; manual event-risk review required.")
        if contract["days_to_expiration"] < self.settings.min_option_days_to_expiration:
            reasons.append("Expiration is too close.")
        if contract["days_to_expiration"] > self.settings.max_option_days_to_expiration:
            reasons.append("Expiration is too far for this review profile.")
        if contract["max_loss_dollars"] is None:
            reasons.append("Max loss is unavailable.")
        if max_contract_price is not None and ask > max_contract_price:
            reasons.append("Ask exceeds configured max contract price.")

        enriched = dict(contract)
        enriched["spread_pct"] = round(spread_pct, 4) if spread_pct is not None else None
        enriched["quality_status"] = "REJECTED" if reasons else "ACCEPTABLE"
        enriched["reasons"] = reasons
        enriched["closest_to_pass_reason"] = self._closest_to_pass_reason(enriched, reasons, max_contract_price)
        return enriched

    def _liquidity_gate(self, contract: dict[str, Any]) -> dict[str, Any]:
        bid = float(contract.get("bid") or 0)
        ask = float(contract.get("ask") or 0)
        midpoint = contract.get("midpoint") or ((bid + ask) / 2 if bid > 0 and ask > 0 else 0.0)
        spread_abs = round(ask - bid, 4) if ask >= bid and bid > 0 else None
        spread_pct_mid = round((ask - bid) / midpoint, 4) if midpoint and bid > 0 and ask >= bid else None
        reasons = list(contract.get("reasons") or [])
        passed = contract.get("quality_status") == "ACCEPTABLE"
        return {
            "status": "LIQUIDITY_GATE_PASS" if passed else "LIQUIDITY_GATE_BLOCK",
            "spread_abs": spread_abs,
            "spread_pct_mid": spread_pct_mid,
            "bid_size": contract.get("bid_size"),
            "ask_size": contract.get("ask_size"),
            "volume": contract.get("volume"),
            "open_interest": contract.get("open_interest"),
            "max_loss_dollars": contract.get("max_loss_dollars"),
            "reason_codes": reasons,
        }

    def _snapshot_mismatch_codes(
        self,
        *,
        symbol: str,
        contract_symbol: str,
        displayed_symbol: str,
        expected_contract_symbol: str,
        bid: float,
        ask: float,
        quote_age_seconds: float | None,
        is_adjusted: bool,
        event_flags: list[str],
    ) -> list[str]:
        codes: list[str] = []
        if not symbol:
            codes.append("MISSING_UNDERLYING")
        if not contract_symbol:
            codes.append("MISSING_CONTRACT_SYMBOL")
        if expected_contract_symbol and contract_symbol and expected_contract_symbol != contract_symbol:
            codes.append("BROKER_CONTRACT_MISMATCH")
        if displayed_symbol and contract_symbol and displayed_symbol != contract_symbol:
            codes.append("DISPLAYED_SYMBOL_MISMATCH")
        if bid <= 0 or ask <= 0 or ask < bid:
            codes.append("INVALID_BID_ASK")
        if quote_age_seconds is not None and quote_age_seconds > 60:
            codes.append("STALE_OPTION_QUOTE")
        if is_adjusted:
            codes.append("ADJUSTED_CONTRACT")
        for flag in event_flags:
            codes.append(f"EVENT_FLAG_{flag.upper()}")
        return codes

    def _event_flags(self, snapshot: dict[str, Any], is_adjusted: bool) -> list[str]:
        flags: list[str] = []
        for key in ["earnings_window", "ex_div_window", "halted", "luld", "expiration_day", "zero_dte"]:
            raw = snapshot.get(key)
            if str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}:
                flags.append(key)
        if is_adjusted:
            flags.append("adjusted_contract")
        return sorted(set(flags))

    def _log_no_trade(self, ticker: str, reasons: list[str], side: str) -> dict:
        result = {
            "ticker": ticker,
            "direction": "put" if side == "puts" else "call",
            "status": "NO_TRADE_PLAN",
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "chain_provider": "yfinance",
            "quality_gate": {
                "bid_ask_spread": False,
                "volume": False,
                "open_interest": False,
                "expiration_risk": False,
                "max_loss": False,
            },
            "accepted_contracts": [],
            "rejected_sample": [],
            "best_rejected_contracts": [],
            "reasons": reasons,
        }
        return self.events.log("options_chain_validation", result)

    def _quality_gate_from_reasons(self, reasons: list[str]) -> dict:
        return {
            "bid_ask_spread": not any(reason in reasons for reason in ["Bid/ask missing or invalid.", "Midpoint missing.", "Bid/ask spread too wide."]),
            "volume": "Contract volume below floor." not in reasons,
            "open_interest": "Open interest below floor." not in reasons,
            "expiration_risk": not any(reason in reasons for reason in ["Expiration is too close.", "Expiration is too far for this review profile."]),
            "max_loss": not any(reason in reasons for reason in ["Max loss is unavailable.", "Ask exceeds configured max contract price."]),
            "contract_identity": not any(reason in reasons for reason in ["BROKER_CONTRACT_MISMATCH", "DISPLAYED_SYMBOL_MISMATCH", "ADJUSTED_CONTRACT", "Adjusted/non-standard contract requires separate OCC/manual review."]),
            "freshness": "STALE_OPTION_QUOTE" not in reasons,
        }

    def _quality_gate_summary(self, scored_contracts: list[dict[str, Any]]) -> dict:
        if not scored_contracts:
            return {
                "bid_ask_spread": False,
                "volume": False,
                "open_interest": False,
                "expiration_risk": False,
                "max_loss": False,
            }
        per_contract = [self._quality_gate_from_reasons(contract.get("reasons", [])) for contract in scored_contracts]
        return {
            gate: any(contract_gates[gate] for contract_gates in per_contract)
            for gate in ["bid_ask_spread", "volume", "open_interest", "expiration_risk", "max_loss"]
        }

    def _rejected_sort_key(self, contract: dict[str, Any]) -> tuple:
        ask = float(contract.get("ask") or 999999)
        spread = contract.get("spread_pct")
        spread_value = float(spread) if spread is not None else 999999.0
        volume = int(contract.get("volume") or 0)
        open_interest = int(contract.get("open_interest") or 0)
        reason_count = len(contract.get("reasons") or [])
        return (reason_count, ask, spread_value, -volume, -open_interest)

    def _closest_to_pass_reason(self, contract: dict[str, Any], reasons: list[str], max_contract_price: float | None) -> str | None:
        if not reasons:
            return None
        if "Bid/ask missing or invalid." in reasons:
            return "Needs positive bid and ask with ask >= bid."
        if "Bid/ask spread too wide." in reasons:
            return f"Would pass spread gate if spread_pct <= {self.settings.max_option_spread_pct}; current spread_pct = {contract.get('spread_pct')}."
        if "Ask exceeds configured max contract price." in reasons:
            return f"Would pass max-price gate if ask <= {max_contract_price}; current ask = {contract.get('ask')}."
        if "Contract volume below floor." in reasons:
            return f"Would pass volume gate if volume >= {self.settings.min_option_volume}; current volume = {contract.get('volume')}."
        if "Open interest below floor." in reasons:
            return f"Would pass open-interest gate if OI >= {self.settings.min_option_open_interest}; current OI = {contract.get('open_interest')}."
        if "Expiration is too close." in reasons:
            return f"Would pass expiration gate if DTE >= {self.settings.min_option_days_to_expiration}; current DTE = {contract.get('days_to_expiration')}."
        if "Expiration is too far for this review profile." in reasons:
            return f"Would pass expiration gate if DTE <= {self.settings.max_option_days_to_expiration}; current DTE = {contract.get('days_to_expiration')}."
        if "Max loss is unavailable." in reasons:
            return "Needs an ask price so max loss can be calculated."
        return "Multiple gates need improvement before this contract can pass."

    def _parse_timestamp(self, value: Any) -> datetime | None:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, datetime):
            return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
        raw = str(value).strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None

    def _parse_expiration(self, value: str) -> date | None:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    def _float(self, value: Any) -> float | None:
        try:
            return None if value is None or value != value else float(value)
        except Exception:
            return None

    def _int(self, value: Any) -> int | None:
        try:
            return None if value is None or value != value else int(value)
        except Exception:
            return None
