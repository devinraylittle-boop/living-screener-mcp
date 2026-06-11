from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import Settings
from app.storage.repositories import EventRepository


class OptionsService:
    def __init__(self, settings: Settings, events: EventRepository):
        self.settings = settings
        self.events = events

    def validate_chain(self, ticker: str, direction: str = "call", max_contract_price: float | None = None) -> dict:
        symbol = ticker.upper()
        side = "puts" if direction.lower() in {"put", "puts", "short"} else "calls"
        provider_status = self.options_data_status()
        provider = provider_status["configured_provider"]
        try:
            contracts, chain_provider = self._load_provider_chain(symbol, side)
        except Exception as exc:
            return self._log_no_trade(
                symbol,
                [f"Options-chain provider failed safely: {type(exc).__name__}."],
                side,
                chain_provider=provider,
                options_truth_status=provider_status,
            )

        if not contracts:
            return self._log_no_trade(
                symbol,
                ["Options-chain data missing or unavailable."],
                side,
                chain_provider=chain_provider,
                options_truth_status=provider_status,
            )

        candidates = [self._score_contract(contract, max_contract_price) for contract in contracts]
        accepted = [contract for contract in candidates if contract["quality_status"] == "ACCEPTABLE"]
        rejected = [contract for contract in candidates if contract["quality_status"] != "ACCEPTABLE"]
        best_rejected = sorted(rejected, key=self._rejected_sort_key)[: self.settings.max_option_contracts_returned]
        truth_gate = self._options_truth_gate(chain_provider=chain_provider, broker_snapshot_validated=False)
        result = {
            "ticker": symbol,
            "direction": "put" if side == "puts" else "call",
            "status": "OPTIONS_CHAIN_ACCEPTABLE" if accepted else "NO_TRADE_PLAN",
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "chain_provider": chain_provider,
            "options_data_status": provider_status,
            "real_money_options_truth_gate": truth_gate,
            "quality_gate": self._quality_gate_summary(candidates),
            "accepted_contracts": accepted[: self.settings.max_option_contracts_returned],
            "rejected_sample": rejected[: self.settings.max_option_contracts_returned],
            "best_rejected_contracts": best_rejected,
            "notes": self._chain_notes(chain_provider, truth_gate),
        }
        return self.events.log("options_chain_validation", result)

    def options_data_status(self) -> dict[str, Any]:
        provider = (self.settings.options_data_provider or "manual").strip().lower()
        if provider in {"marketdata", "marketdata.app", "market_data"}:
            normalized = "marketdata"
            automated_ready = bool(self.settings.marketdata_api_key)
            provider_label = "MarketData.app"
        elif provider == "tradier":
            normalized = "tradier"
            automated_ready = bool(self.settings.tradier_access_token)
            provider_label = "Tradier"
        elif provider in {"yfinance", "yahoo"}:
            normalized = "yfinance"
            automated_ready = False
            provider_label = "yfinance preliminary"
        else:
            normalized = "manual"
            automated_ready = False
            provider_label = "manual broker snapshot"
        return {
            "schema_version": "options_data_status_v1",
            "configured_provider": normalized,
            "provider_label": provider_label,
            "options_realtime_required": self.settings.options_realtime_required,
            "max_option_quote_age_seconds": self.settings.max_option_quote_age_seconds,
            "has_marketdata_api_key": bool(self.settings.marketdata_api_key),
            "has_tradier_access_token": bool(self.settings.tradier_access_token),
            "automated_realtime_options_available": automated_ready,
            "real_money_options_truth_status": "AUTOMATED_OPTIONS_TRUTH_READY" if automated_ready else "BROKER_SNAPSHOT_REQUIRED",
            "broker_snapshot_required": not automated_ready,
            "yfinance_chain_is_preliminary": True,
            "supported_automated_providers": ["marketdata", "tradier"],
            "manual_sources_allowed": ["broker_visible_option_snapshot"],
            "blocked_sources_for_real_money_truth": ["yfinance", "robinhood_level_2_equity_only", "stale_screenshots"],
            "next_step": (
                "Automated options truth is configured; validate quote freshness and chain liquidity."
                if automated_ready
                else "Use manual broker snapshot validation or configure MARKETDATA_API_KEY/TRADIER_ACCESS_TOKEN before treating options as real-money ready."
            ),
            "review_only": True,
            "can_place_order_from_this_mcp": False,
        }

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
            "options_data_status": self.options_data_status(),
            "real_money_options_truth_gate": self._options_truth_gate("broker_snapshot_manual", accepted),
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

    def _load_provider_chain(self, ticker: str, side: str) -> tuple[list[dict[str, Any]], str]:
        provider = (self.settings.options_data_provider or "manual").strip().lower()
        if provider in {"marketdata", "marketdata.app", "market_data"}:
            if not self.settings.marketdata_api_key:
                raise RuntimeError("MARKETDATA_API_KEY missing")
            return self._load_marketdata_chain(ticker, side), "marketdata"
        if provider == "tradier":
            if not self.settings.tradier_access_token:
                raise RuntimeError("TRADIER_ACCESS_TOKEN missing")
            return self._load_tradier_chain(ticker, side), "tradier"
        return self._load_yfinance_chain(ticker, side), "yfinance_preliminary"

    def _load_marketdata_chain(self, ticker: str, side: str) -> list[dict[str, Any]]:
        side_name = "put" if side == "puts" else "call"
        query = urlencode({"side": side_name})
        url = f"https://api.marketdata.app/v1/options/chain/{ticker}/?{query}"
        payload = self._get_json(url, {"Authorization": f"Bearer {self.settings.marketdata_api_key}", "Accept": "application/json"}, {200, 203})
        return [
            contract
            for contract in self._normalize_marketdata_chain(ticker, payload)
            if (contract.get("side") or side_name) == side_name
            and self.settings.min_option_days_to_expiration <= int(contract.get("days_to_expiration") or 0) <= self.settings.max_option_days_to_expiration
        ]

    def _load_tradier_chain(self, ticker: str, side: str) -> list[dict[str, Any]]:
        contracts: list[dict[str, Any]] = []
        side_name = "put" if side == "puts" else "call"
        for expiration in self._tradier_expirations(ticker):
            dte = self._days_to_expiration(expiration)
            if dte is None or dte < self.settings.min_option_days_to_expiration or dte > self.settings.max_option_days_to_expiration:
                continue
            query = urlencode({"symbol": ticker, "expiration": expiration, "greeks": "true"})
            url = f"{self.settings.tradier_base_url}/markets/options/chains?{query}"
            payload = self._get_json(url, {"Authorization": f"Bearer {self.settings.tradier_access_token}", "Accept": "application/json"}, {200})
            contracts.extend(
                contract
                for contract in self._normalize_tradier_chain(ticker, expiration, dte, payload)
                if (contract.get("side") or side_name) == side_name
            )
            if len(contracts) >= self.settings.max_option_contracts_returned * 10:
                break
        return contracts

    def _tradier_expirations(self, ticker: str) -> list[str]:
        query = urlencode({"symbol": ticker, "includeAllRoots": "false", "strikes": "false"})
        url = f"{self.settings.tradier_base_url}/markets/options/expirations?{query}"
        payload = self._get_json(url, {"Authorization": f"Bearer {self.settings.tradier_access_token}", "Accept": "application/json"}, {200})
        expirations = ((payload.get("expirations") or {}).get("date") if isinstance(payload, dict) else None) or []
        if isinstance(expirations, str):
            return [expirations]
        return [str(item) for item in expirations if item]

    def _get_json(self, url: str, headers: dict[str, str], success_codes: set[int]) -> dict[str, Any]:
        request = Request(url, headers=headers)
        with urlopen(request, timeout=12) as response:
            if response.status not in success_codes:
                raise RuntimeError(f"HTTP {response.status}")
            return json.loads(response.read().decode("utf-8"))

    def _normalize_marketdata_chain(self, ticker: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        symbols = payload.get("optionSymbol")
        if isinstance(symbols, list):
            return [self._marketdata_contract_from_columns(ticker, payload, index) for index in range(len(symbols))]
        if isinstance(payload.get("data"), list):
            return [self._marketdata_contract_from_row(ticker, row) for row in payload["data"] if isinstance(row, dict)]
        if isinstance(payload.get("option"), list):
            return [self._marketdata_contract_from_row(ticker, row) for row in payload["option"] if isinstance(row, dict)]
        return []

    def _marketdata_contract_from_columns(self, ticker: str, payload: dict[str, Any], index: int) -> dict[str, Any]:
        def pick(name: str, default: Any = None) -> Any:
            values = payload.get(name)
            return values[index] if isinstance(values, list) and index < len(values) else default

        expiration = self._date_from_epoch_or_iso(pick("expiration"))
        bid = self._float(pick("bid")) or 0.0
        ask = self._float(pick("ask")) or 0.0
        dte = self._int(pick("dte")) or self._days_to_expiration(expiration) or 0
        return {
            "contract_symbol": str(pick("optionSymbol") or ""),
            "ticker": str(pick("underlying") or ticker).upper(),
            "side": str(pick("side") or "").lower(),
            "expiration": expiration,
            "days_to_expiration": dte,
            "strike": self._float(pick("strike")),
            "bid": bid,
            "ask": ask,
            "bid_size": self._int(pick("bidSize")),
            "ask_size": self._int(pick("askSize")),
            "last_price": self._float(pick("last")) or 0.0,
            "midpoint": self._float(pick("mid")) or (round((bid + ask) / 2, 4) if bid > 0 and ask > 0 else None),
            "volume": self._int(pick("volume")) or 0,
            "open_interest": self._int(pick("openInterest")) or self._int(pick("open_interest")) or 0,
            "implied_volatility": self._float(pick("iv")),
            "max_loss_dollars": round(ask * 100, 2) if ask > 0 else None,
            "break_even": None,
            "quote_age_seconds": self._quote_age_from_updated(pick("updated")),
            "source": "marketdata",
        }

    def _marketdata_contract_from_row(self, ticker: str, row: dict[str, Any]) -> dict[str, Any]:
        bid = self._float(row.get("bid")) or 0.0
        ask = self._float(row.get("ask")) or 0.0
        expiration = self._date_from_epoch_or_iso(row.get("expiration"))
        return {
            "contract_symbol": str(row.get("optionSymbol") or row.get("symbol") or ""),
            "ticker": str(row.get("underlying") or ticker).upper(),
            "side": str(row.get("side") or "").lower(),
            "expiration": expiration,
            "days_to_expiration": self._int(row.get("dte")) or self._days_to_expiration(expiration) or 0,
            "strike": self._float(row.get("strike")),
            "bid": bid,
            "ask": ask,
            "bid_size": self._int(row.get("bidSize") or row.get("bid_size")),
            "ask_size": self._int(row.get("askSize") or row.get("ask_size")),
            "last_price": self._float(row.get("last")) or self._float(row.get("lastPrice")) or 0.0,
            "midpoint": self._float(row.get("mid")) or (round((bid + ask) / 2, 4) if bid > 0 and ask > 0 else None),
            "volume": self._int(row.get("volume")) or 0,
            "open_interest": self._int(row.get("openInterest") or row.get("open_interest")) or 0,
            "implied_volatility": self._float(row.get("iv") or row.get("impliedVolatility")),
            "max_loss_dollars": round(ask * 100, 2) if ask > 0 else None,
            "break_even": None,
            "quote_age_seconds": self._quote_age_from_updated(row.get("updated")),
            "source": "marketdata",
        }

    def _normalize_tradier_chain(self, ticker: str, expiration: str, dte: int, payload: dict[str, Any]) -> list[dict[str, Any]]:
        options = ((payload.get("options") or {}).get("option") if isinstance(payload, dict) else None) or []
        if isinstance(options, dict):
            options = [options]
        contracts: list[dict[str, Any]] = []
        for row in options:
            if not isinstance(row, dict):
                continue
            bid = self._float(row.get("bid")) or 0.0
            ask = self._float(row.get("ask")) or 0.0
            contracts.append(
                {
                    "contract_symbol": str(row.get("symbol") or ""),
                    "ticker": ticker.upper(),
                    "side": str(row.get("option_type") or "").lower(),
                    "expiration": expiration,
                    "days_to_expiration": dte,
                    "strike": self._float(row.get("strike")),
                    "bid": bid,
                    "ask": ask,
                    "bid_size": self._int(row.get("bidsize")),
                    "ask_size": self._int(row.get("asksize")),
                    "last_price": self._float(row.get("last")) or 0.0,
                    "midpoint": round((bid + ask) / 2, 4) if bid > 0 and ask > 0 else self._float(row.get("last")),
                    "volume": self._int(row.get("volume")) or 0,
                    "open_interest": self._int(row.get("open_interest")) or 0,
                    "implied_volatility": self._float((row.get("greeks") or {}).get("mid_iv") if isinstance(row.get("greeks"), dict) else None),
                    "max_loss_dollars": round(ask * 100, 2) if ask > 0 else None,
                    "break_even": None,
                    "source": "tradier",
                }
            )
        return contracts

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
        quote_age = contract.get("quote_age_seconds")
        if quote_age is not None and float(quote_age) > self.settings.max_option_quote_age_seconds:
            reasons.append("Option quote is stale.")
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

    def _options_truth_gate(self, chain_provider: str, broker_snapshot_validated: bool) -> dict[str, Any]:
        realtime_provider = chain_provider in {"marketdata", "tradier"}
        manual_snapshot = chain_provider == "broker_snapshot_manual"
        ready = realtime_provider or (manual_snapshot and broker_snapshot_validated)
        return {
            "schema_version": "real_money_options_truth_gate_v1",
            "status": "REAL_MONEY_OPTIONS_TRUTH_READY" if ready else "BROKER_SNAPSHOT_REQUIRED",
            "chain_provider": chain_provider,
            "automated_realtime_provider": realtime_provider,
            "broker_snapshot_validated": bool(broker_snapshot_validated),
            "preliminary_only": chain_provider in {"yfinance", "yfinance_preliminary"},
            "allowed_for_review_ranking": True,
            "allowed_for_real_money_without_fresh_broker_snapshot": ready,
            "reason": (
                "Automated realtime options provider or fresh broker-visible snapshot is available."
                if ready
                else "This options chain may support research/review, but real-money readiness requires MarketData/Tradier or a fresh broker-visible snapshot."
            ),
        }

    def _chain_notes(self, chain_provider: str, truth_gate: dict[str, Any]) -> list[str]:
        notes = ["Review-only options quality check. This MCP cannot place orders."]
        if chain_provider == "yfinance_preliminary":
            notes.append("yfinance options data is preliminary and not sufficient as real-money options truth.")
        if truth_gate.get("status") != "REAL_MONEY_OPTIONS_TRUTH_READY":
            notes.append("Before any manual broker action, validate a fresh broker-visible option snapshot or configure MarketData/Tradier.")
        return notes

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

    def _log_no_trade(
        self,
        ticker: str,
        reasons: list[str],
        side: str,
        chain_provider: str = "yfinance_preliminary",
        options_truth_status: dict[str, Any] | None = None,
    ) -> dict:
        truth_status = options_truth_status or self.options_data_status()
        truth_gate = self._options_truth_gate(chain_provider, False)
        result = {
            "ticker": ticker,
            "direction": "put" if side == "puts" else "call",
            "status": "NO_TRADE_PLAN",
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "chain_provider": chain_provider,
            "options_data_status": truth_status,
            "real_money_options_truth_gate": truth_gate,
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
            "notes": self._chain_notes(chain_provider, truth_gate),
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
            "freshness": not any(reason in reasons for reason in ["STALE_OPTION_QUOTE", "Option quote is stale."]),
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

    def _date_from_epoch_or_iso(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=UTC).date().isoformat()
        raw = str(value).strip()
        if not raw:
            return None
        try:
            if raw.isdigit():
                return datetime.fromtimestamp(float(raw), tz=UTC).date().isoformat()
            return date.fromisoformat(raw[:10]).isoformat()
        except ValueError:
            return None

    def _days_to_expiration(self, value: Any) -> int | None:
        expiration = self._date_from_epoch_or_iso(value)
        if not expiration:
            return None
        try:
            return (date.fromisoformat(expiration) - datetime.now(UTC).date()).days
        except ValueError:
            return None

    def _quote_age_from_updated(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            updated = datetime.fromtimestamp(float(value), tz=UTC)
            return round((datetime.now(UTC) - updated).total_seconds(), 3)
        except Exception:
            parsed = self._parse_timestamp(value)
            return round((datetime.now(UTC) - parsed).total_seconds(), 3) if parsed else None

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
