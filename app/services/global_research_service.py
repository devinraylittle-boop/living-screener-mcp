from __future__ import annotations

from datetime import UTC, datetime
from statistics import mean
from typing import Any

from app.storage.repositories import EventRepository


class GlobalResearchService:
    """Off-hours underlying-only research scans for crypto and global markets."""

    default_universes = {
        "crypto": ("BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD"),
        "asia": ("^N225", "^HSI", "EWJ", "FXI", "MCHI", "AAXJ"),
        "europe": ("^FTSE", "^GDAXI", "^FCHI", "EWU", "EWG", "FEZ"),
        "global": ("BTC-USD", "ETH-USD", "SOL-USD", "^N225", "^HSI", "^FTSE", "EWJ", "FEZ"),
    }

    def __init__(self, events: EventRepository):
        self.events = events

    def offhours_plan(self) -> dict:
        payload = {
            "status": "OFFHOURS_RESEARCH_READY",
            "mission": "Keep learning when U.S. options liquidity is stale or closed.",
            "use_cases": [
                "Crypto paper/backtest research because crypto trades continuously.",
                "Foreign index/ETF movement study for overnight regime context.",
                "Underlying-only technical pattern research; do not infer U.S. options tradability from foreign/crypto scans.",
                "Feed later outcomes into the mistake engine as research labels.",
            ],
            "universes": self.default_universes,
            "recommended_now": [
                "Run crypto paper backtests on ETH-USD and SOL-USD with BTC/DOGE excluded until they stop leaking.",
                "Run global research scans on crypto/global universes to study compression, expansion, trend, and RVOL.",
                "Log promising study candidates, then check outcomes later before changing rules.",
            ],
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
            "notes": "This is research only. It does not recommend broker action and does not validate U.S. options chains.",
        }
        return self.events.log("offhours_research_plan", payload)

    def run_global_research_scan(
        self,
        market: str = "global",
        symbols: list[str] | None = None,
        period: str = "5d",
        interval: str = "5m",
        max_candidates: int = 20,
    ) -> dict:
        universe = self._symbols(market, symbols)
        results = []
        errors = []
        for symbol in universe:
            try:
                candles = self._load_yfinance_candles(symbol, period, interval)
                results.append(self._evaluate_symbol(symbol, candles, interval))
            except Exception as exc:
                errors.append({"symbol": symbol, "error": type(exc).__name__})
                results.append(self._empty_symbol(symbol, f"Data load failed safely: {type(exc).__name__}."))

        ranked = sorted(results, key=lambda item: item["score"], reverse=True)[: max(1, min(int(max_candidates), 50))]
        payload = {
            "status": "GLOBAL_RESEARCH_SCAN_COMPLETE",
            "market": market,
            "period": period,
            "interval": interval,
            "symbols": universe,
            "top_candidates": [item for item in ranked if item["status"] == "STUDY_CANDIDATE"],
            "watch_list": [item for item in ranked if item["status"] == "WATCH_ONLY"],
            "pass_list": [item for item in ranked if item["status"] == "PASS"],
            "errors": errors,
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
            "notes": [
                "Underlying-only off-hours research. No options chain is validated here.",
                "Use this to study movement quality and feed future outcomes into the mistake engine.",
            ],
        }
        return self.events.log("global_research_scan", payload)

    def _evaluate_symbol(self, symbol: str, candles: list[dict[str, Any]], interval: str) -> dict:
        if len(candles) < 30:
            return self._empty_symbol(symbol, "Not enough candles for off-hours research scan.")

        closes = [float(candle["close"]) for candle in candles]
        highs = [float(candle["high"]) for candle in candles]
        lows = [float(candle["low"]) for candle in candles]
        volumes = [float(candle["volume"]) for candle in candles]
        latest = candles[-1]
        first_close = closes[0]
        latest_close = closes[-1]
        recent_anchor = closes[-6] if len(closes) >= 6 else closes[-2]
        trend_pct = (latest_close - first_close) / first_close if first_close else 0.0
        recent_trend_pct = (latest_close - recent_anchor) / recent_anchor if recent_anchor else 0.0
        relative_volume = self._relative_volume(volumes)
        range_expansion, expansion_source = self._range_expansion(highs, lows, closes)
        compression_break = self._compression_break(highs, lows, closes)
        close_location = self._close_location(latest_close, highs[-20:], lows[-20:])
        direction = "long" if recent_trend_pct >= 0 else "short"
        score = self._score(trend_pct, recent_trend_pct, relative_volume, range_expansion, compression_break, close_location)
        status = "STUDY_CANDIDATE" if score >= 65 else "WATCH_ONLY" if score >= 50 else "PASS"
        return {
            "symbol": symbol.upper(),
            "status": status,
            "score": score,
            "direction": direction,
            "latest_close": round(latest_close, 6),
            "timestamp": latest["timestamp"],
            "interval": interval,
            "feature_summary": {
                "trend_pct": round(trend_pct, 5),
                "recent_trend_pct": round(recent_trend_pct, 5),
                "relative_volume": round(relative_volume, 3) if relative_volume is not None else None,
                "relative_volume_status": "available" if relative_volume is not None else "unavailable_or_zero_volume",
                "range_expansion": round(range_expansion, 3) if range_expansion is not None else None,
                "range_expansion_source": expansion_source,
                "compression_break": compression_break,
                "close_location_20": round(close_location, 3),
                "candle_count": len(candles),
            },
            "lesson_tags": self._lesson_tags(relative_volume, range_expansion, compression_break, close_location),
            "research_use": "Study only; later compare against 15m/30m/1h outcome before promoting rules.",
            "review_only": True,
            "order_allowed": False,
            "options_chain_quality": "NOT_VALIDATED",
            "can_place_order_from_this_mcp": False,
        }

    def _score(
        self,
        trend_pct: float,
        recent_trend_pct: float,
        relative_volume: float | None,
        range_expansion: float | None,
        compression_break: bool,
        close_location: float,
    ) -> float:
        score = 0.0
        if abs(trend_pct) >= 0.015:
            score += 18
        if abs(recent_trend_pct) >= 0.003:
            score += 18
        if relative_volume is not None and relative_volume >= 1.5:
            score += 18
        elif relative_volume is not None and relative_volume >= 1.1:
            score += 10
        if range_expansion is not None and range_expansion >= 1.4:
            score += 16
        elif range_expansion is not None and range_expansion >= 1.1:
            score += 8
        if compression_break:
            score += 18
        if close_location >= 0.8 or close_location <= 0.2:
            score += 12
        if abs(recent_trend_pct) < 0.001 and relative_volume is not None and relative_volume < 1.0:
            score -= 12
        return round(max(0.0, min(100.0, score)), 2)

    def _relative_volume(self, volumes: list[float]) -> float | None:
        if len(volumes) < 21:
            return None
        baseline = mean(volume for volume in volumes[-21:-1] if volume >= 0)
        latest = volumes[-1]
        if baseline <= 0 or latest <= 0:
            return None
        return latest / baseline

    def _range_expansion(self, highs: list[float], lows: list[float], closes: list[float]) -> tuple[float | None, str]:
        if len(closes) < 21:
            return None, "unavailable_insufficient_candles"
        ranges = [max(highs[index] - lows[index], 0.0) for index in range(len(closes))]
        baseline = mean(ranges[-21:-1])
        if baseline > 0 and ranges[-1] > 0:
            return ranges[-1] / baseline, "high_low_range"
        close_move_expansion = self._close_move_expansion(closes)
        if close_move_expansion is not None:
            return close_move_expansion, "close_to_close_proxy"
        return None, "unavailable_zero_range"

    def _close_move_expansion(self, closes: list[float]) -> float | None:
        if len(closes) < 22:
            return None
        moves = [
            abs((closes[index] - closes[index - 1]) / closes[index - 1])
            for index in range(1, len(closes))
            if closes[index - 1] > 0
        ]
        if len(moves) < 21:
            return None
        baseline = mean(moves[-21:-1])
        latest = moves[-1]
        if baseline <= 0 or latest <= 0:
            return None
        return latest / baseline

    def _compression_break(self, highs: list[float], lows: list[float], closes: list[float]) -> bool:
        if len(closes) < 31:
            return False
        recent_range = max(highs[-7:-1]) - min(lows[-7:-1])
        prior_range = max(highs[-31:-7]) - min(lows[-31:-7])
        if prior_range <= 0:
            return False
        was_compressed = recent_range / prior_range <= 0.45
        breaks_recent_high = closes[-1] > max(highs[-7:-1])
        breaks_recent_low = closes[-1] < min(lows[-7:-1])
        return bool(was_compressed and (breaks_recent_high or breaks_recent_low))

    def _close_location(self, close: float, highs: list[float], lows: list[float]) -> float:
        high = max(highs)
        low = min(lows)
        return (close - low) / (high - low) if high > low else 0.5

    def _lesson_tags(self, relative_volume: float | None, range_expansion: float | None, compression_break: bool, close_location: float) -> list[str]:
        tags = []
        if relative_volume is None:
            tags.append("rvol_unavailable")
        elif relative_volume >= 1.5:
            tags.append("rvol_expansion")
        elif relative_volume < 1.0:
            tags.append("low_rvol")
        if range_expansion is None:
            tags.append("range_unavailable")
        elif range_expansion >= 1.4:
            tags.append("range_expansion")
        if compression_break:
            tags.append("compression_break")
        if close_location >= 0.8:
            tags.append("near_range_high")
        if close_location <= 0.2:
            tags.append("near_range_low")
        return tags

    def _load_yfinance_candles(self, symbol: str, period: str, interval: str) -> list[dict[str, Any]]:
        import yfinance as yf

        history = yf.Ticker(symbol).history(period=period, interval=interval, prepost=True)
        if history is None or history.empty:
            return []
        candles = []
        for timestamp, row in history.iterrows():
            open_price = self._float(row.get("Open"))
            high = self._float(row.get("High"))
            low = self._float(row.get("Low"))
            close = self._float(row.get("Close"))
            if any(value is None or value <= 0 for value in [open_price, high, low, close]):
                continue
            candles.append(
                {
                    "timestamp": self._timestamp(timestamp),
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": self._float(row.get("Volume")) or 0.0,
                }
            )
        return candles

    def _symbols(self, market: str, symbols: list[str] | None) -> list[str]:
        raw = symbols or list(self.default_universes.get(market.lower(), self.default_universes["global"]))
        output = []
        for symbol in raw:
            normalized = str(symbol).upper().strip()
            if normalized and normalized not in output:
                output.append(normalized)
        return output[:20]

    def _empty_symbol(self, symbol: str, reason: str) -> dict:
        return {
            "symbol": symbol.upper(),
            "status": "PASS",
            "score": 0.0,
            "direction": "none",
            "reason": reason,
            "review_only": True,
            "order_allowed": False,
            "can_place_order_from_this_mcp": False,
        }

    def _float(self, value: Any) -> float | None:
        try:
            return None if value is None or value != value else float(value)
        except Exception:
            return None

    def _timestamp(self, value: Any) -> str:
        if hasattr(value, "to_pydatetime"):
            value = value.to_pydatetime()
        if isinstance(value, datetime):
            timestamp = value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
            return timestamp.isoformat()
        return datetime.now(UTC).isoformat()
