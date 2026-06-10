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
        contract = {
            "contract_symbol": str(snapshot.get("contract_symbol") or snapshot.get("symbol") or ""),
            "ticker": symbol,
            "expiration": snapshot.get("expiration"),
            "days_to_expiration": self._int(snapshot.get("days_to_expiration", snapshot.get("dte"))) or 0,
            "strike": self._float(snapshot.get("strike")),
            "bid": bid,
            "ask": ask,
            "last_price": last,
            "midpoint": round((bid + ask) / 2, 4) if bid > 0 and ask > 0 else last,
            "volume": self._int(snapshot.get("volume")) or 0,
            "open_interest": self._int(snapshot.get("open_interest", snapshot.get("openInterest"))) or 0,
            "implied_volatility": self._float(snapshot.get("implied_volatility", snapshot.get("iv"))),
            "max_loss_dollars": round(ask * 100, 2) if ask > 0 else None,
            "break_even": None,
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
        accepted = scored["quality_status"] == "ACCEPTABLE"
        result = {
            "ticker": symbol,
            "direction": "put" if side == "puts" else "call",
            "status": "OPTIONS_CHAIN_ACCEPTABLE" if accepted else "NO_TRADE_PLAN",
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "chain_provider": "broker_snapshot_manual",
            "max_contract_price_used": max_contract_price,
            "quality_gate": self._quality_gate_from_reasons(scored["reasons"]),
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
