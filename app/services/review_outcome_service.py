from __future__ import annotations

from datetime import UTC, datetime
from statistics import mean
from typing import Any

from app.config import Settings
from app.data_adapters.base import MarketDataAdapter
from app.models.schemas import Candle, Quote
from app.storage.repositories import EventRepository


class ReviewOutcomeService:
    def __init__(self, settings: Settings, events: EventRepository, market_data: MarketDataAdapter | None):
        self.settings = settings
        self.events = events
        self.market_data = market_data

    def log_review_decision(self, decision: dict[str, Any]) -> dict:
        payload = {
            "review_id": decision.get("review_id") or self._review_id(decision),
            "ticker": str(decision.get("ticker", "")).upper(),
            "direction": self._normalize_direction(str(decision.get("direction", ""))),
            "entry_reference": self._float(decision.get("entry_reference", decision.get("price"))),
            "review_timestamp": self._timestamp_or_now(decision.get("review_timestamp", decision.get("timestamp"))),
            "strategy": decision.get("strategy", "review_only"),
            "contract_symbol": decision.get("contract_symbol"),
            "notes": decision.get("notes", ""),
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
            "raw_decision": decision,
        }
        return self.events.log("review_decision", payload)

    def check_review_outcome(self, review: dict[str, Any], horizons: dict[str, int] | None = None) -> dict:
        symbol = str(review.get("ticker", "")).upper()
        direction = self._normalize_direction(str(review.get("direction", "")))
        entry = self._float(review.get("entry_reference", review.get("price")))
        if not symbol or entry is None or entry <= 0:
            return self.events.log(
                "review_outcome",
                {
                    "status": "OUTCOME_UNAVAILABLE",
                    "reason": "Ticker and positive entry_reference are required.",
                    "review_only": True,
                    "can_place_order_from_this_mcp": False,
                },
            )
        if self.market_data is None:
            return self.events.log(
                "review_outcome",
                {
                    "ticker": symbol,
                    "status": "OUTCOME_UNAVAILABLE",
                    "reason": "No market data adapter configured.",
                    "review_only": True,
                    "can_place_order_from_this_mcp": False,
                },
            )

        quote = self.market_data.get_quote(symbol)
        candles = self.market_data.get_candles(symbol, self.settings.market_data_interval, self.settings.market_data_period)
        latest_price = self._latest_price(quote, candles)
        if latest_price is None:
            return self.events.log(
                "review_outcome",
                {
                    "ticker": symbol,
                    "status": "OUTCOME_UNAVAILABLE",
                    "reason": "No quote or candle price available.",
                    "review_only": True,
                    "can_place_order_from_this_mcp": False,
                },
            )

        horizon_bars = horizons or {"15m": 3, "30m": 6, "1h": 12}
        review_timestamp = self._parse_timestamp(review.get("review_timestamp", review.get("timestamp")))
        outcome_candles = self._candles_after_review(candles, review_timestamp)
        window_status = "ANCHORED_TO_REVIEW_TIMESTAMP" if review_timestamp else "UNANCHORED_REVIEW_TIME"
        outcome = {
            "review_id": review.get("review_id"),
            "ticker": symbol,
            "direction": direction,
            "review_timestamp": review_timestamp.isoformat() if review_timestamp else None,
            "entry_reference": round(entry, 4),
            "latest_price": round(latest_price, 4),
            "latest_price_source": self._latest_price_source(quote, candles),
            "current_return_pct": self._directional_return(entry, latest_price, direction),
            "horizon_returns": self._horizon_returns(outcome_candles, entry, direction, horizon_bars) if review_timestamp else {label: None for label in horizon_bars},
            "max_favorable_excursion": self._excursion(outcome_candles, entry, direction, favorable=True) if review_timestamp else None,
            "max_adverse_excursion": self._excursion(outcome_candles, entry, direction, favorable=False) if review_timestamp else None,
            "outcome_window_status": window_status,
            "verdict": self._verdict(entry, latest_price, direction),
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
            "notes": "Outcome grading only. This MCP cannot place or cancel broker orders.",
        }
        return self.events.log("review_outcome", outcome)

    def summarize_review_outcomes(self, outcomes: list[dict[str, Any]]) -> dict:
        usable = [item for item in outcomes if item.get("status") != "OUTCOME_UNAVAILABLE" and "current_return_pct" in item]
        wins = [item for item in usable if float(item.get("current_return_pct", 0)) > 0]
        summary = {
            "sample_size": len(usable),
            "win_rate": round(len(wins) / len(usable), 4) if usable else 0.0,
            "average_return_pct": round(mean(float(item.get("current_return_pct", 0)) for item in usable), 5) if usable else 0.0,
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "notes": "Summary is only as good as the supplied outcome payloads.",
        }
        return self.events.log("review_outcome_summary", summary)

    def _latest_price(self, quote: Quote | None, candles: list[Candle]) -> float | None:
        if quote is not None and quote.price > 0 and not quote.is_stale:
            return quote.price
        if candles:
            latest = candles[-1]
            if latest.close > 0:
                return latest.close
        if quote is not None and quote.price > 0:
            return quote.price
        return None

    def _latest_price_source(self, quote: Quote | None, candles: list[Candle]) -> str:
        if quote is not None and quote.price > 0 and not quote.is_stale:
            return "quote"
        if candles and candles[-1].close > 0:
            return "latest_candle_close"
        if quote is not None and quote.price > 0:
            return "stale_quote_fallback"
        return "unavailable"

    def _candles_after_review(self, candles: list[Candle], review_timestamp: datetime | None) -> list[Candle]:
        if review_timestamp is None:
            return []
        return [candle for candle in candles if candle.timestamp >= review_timestamp]

    def _horizon_returns(self, candles: list[Candle], entry: float, direction: str, horizons: dict[str, int]) -> dict[str, float | None]:
        output: dict[str, float | None] = {}
        for label, bars in horizons.items():
            index = int(bars) - 1
            if index < 0 or index >= len(candles):
                output[label] = None
                continue
            output[label] = self._directional_return(entry, candles[index].close, direction)
        return output

    def _excursion(self, candles: list[Candle], entry: float, direction: str, favorable: bool) -> float | None:
        values = []
        for candle in candles:
            price = candle.high if (direction == "long") == favorable else candle.low
            values.append(self._directional_return(entry, price, direction))
        if not values:
            return None
        return round(max(values) if favorable else min(values), 5)

    def _directional_return(self, entry: float, price: float, direction: str) -> float:
        raw = (price - entry) / entry
        if direction == "short":
            raw *= -1
        return round(raw, 5)

    def _verdict(self, entry: float, price: float, direction: str) -> str:
        result = self._directional_return(entry, price, direction)
        if result >= 0.003:
            return "HELPED"
        if result <= -0.003:
            return "HURT"
        return "FLAT"

    def _normalize_direction(self, direction: str) -> str:
        lowered = direction.lower()
        if lowered in {"put", "puts", "short", "bearish"}:
            return "short"
        return "long"

    def _float(self, value: Any) -> float | None:
        try:
            return None if value is None or value != value else float(value)
        except Exception:
            return None

    def _parse_timestamp(self, value: Any) -> datetime | None:
        if value is None:
            return None
        try:
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

    def _timestamp_or_now(self, value: Any) -> str:
        parsed = self._parse_timestamp(value) or datetime.now(UTC)
        return parsed.isoformat()

    def _review_id(self, decision: dict[str, Any]) -> str:
        ticker = str(decision.get("ticker", "UNKNOWN")).upper()
        direction = self._normalize_direction(str(decision.get("direction", "long")))
        entry = decision.get("entry_reference", decision.get("price", "NA"))
        return f"{ticker}-{direction}-{entry}"
