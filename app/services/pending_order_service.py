from __future__ import annotations

from datetime import UTC, datetime

from app.config import Settings
from app.storage.repositories import EventRepository


class PendingOrderService:
    def __init__(self, settings: Settings, events: EventRepository, scanner, options):
        self.settings = settings
        self.events = events
        self.scanner = scanner
        self.options = options

    def review_pending_buy(
        self,
        ticker: str,
        submitted_at: str,
        limit_price: float | None = None,
        is_options_order: bool = False,
        direction: str = "call",
        mode: str = "conservative_review_only",
    ) -> dict:
        symbol = ticker.upper()
        age_seconds = self._age_seconds(submitted_at)
        scan = self.scanner.run_market_scan(mode, [symbol], 1)
        stock_item = (scan["top_candidates"] or scan["pass_list"] or [{}])[0]
        quote = stock_item.get("quote_summary") or {}
        current_price = quote.get("price")
        reasons: list[str] = []
        warnings: list[str] = []

        if age_seconds is None:
            reasons.append("Submitted timestamp could not be parsed; pending order must be reconsidered.")
        elif age_seconds >= self.settings.pending_buy_recheck_seconds:
            reasons.append("Pending buy is older than the configured recheck window.")

        if stock_item.get("status") != "CANDIDATE":
            reasons.append("Current stock setup no longer clears candidate threshold.")

        price_drift = self._price_drift(limit_price, current_price)
        if price_drift is not None and abs(price_drift) > self.settings.max_pending_order_price_drift_pct:
            reasons.append("Current price has drifted beyond the pending-order tolerance.")

        options_gate = None
        if is_options_order:
            options_gate = self.options.validate_chain(symbol, direction, limit_price)
            if options_gate.get("status") != "OPTIONS_CHAIN_ACCEPTABLE":
                reasons.append("Options-chain quality is no longer acceptable.")

        if age_seconds is not None and age_seconds < self.settings.pending_buy_recheck_seconds:
            warnings.append("Pending order is still inside the initial review window.")

        status = "RECONSIDER_PENDING_BUY" if reasons else "STILL_VALID_FOR_REVIEW"
        result = {
            "ticker": symbol,
            "status": status,
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
            "pending_buy_recheck_seconds": self.settings.pending_buy_recheck_seconds,
            "age_seconds": age_seconds,
            "limit_price": limit_price,
            "current_price": current_price,
            "price_drift_pct": price_drift,
            "stock_setup": stock_item,
            "options_chain_validation": options_gate,
            "reasons": reasons,
            "warnings": warnings,
            "next_action": "Recheck with broker/order system before leaving, canceling, or replacing any pending order.",
        }
        return self.events.log("pending_buy_review", result)

    def _age_seconds(self, submitted_at: str) -> int | None:
        try:
            value = submitted_at.strip()
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return max(0, int((datetime.now(UTC) - parsed.astimezone(UTC)).total_seconds()))
        except Exception:
            return None

    def _price_drift(self, limit_price: float | None, current_price: float | None) -> float | None:
        if limit_price is None or current_price is None or limit_price <= 0:
            return None
        return round((float(current_price) - float(limit_price)) / float(limit_price), 5)
