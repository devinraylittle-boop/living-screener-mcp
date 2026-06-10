from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from statistics import mean
from zoneinfo import ZoneInfo

from app.config import Settings
from app.data_adapters.base import MarketDataAdapter
from app.models.schemas import Candle, Quote
from app.storage.repositories import EventRepository, RecommendationRepository
from app.version import BUILD_VERSION


class ScannerService:
    def __init__(self, settings: Settings, events: EventRepository, recommendations: RecommendationRepository, market_data: MarketDataAdapter | None):
        self.settings = settings
        self.events = events
        self.recommendations = recommendations
        self.market_data = market_data

    def run_market_scan(self, mode: str, tickers: list[str] | None = None, max_candidates: int = 25) -> dict:
        universe = self._universe_for_mode(mode, tickers)
        provider_name = self.market_data.name if self.market_data else "none"
        provider_details = getattr(self.market_data, "details", None) if self.market_data else None
        regime = {
            "regime": "review-data-available" if self.market_data else "no-edge",
            "confidence": 0.0,
            "notes": "Provider configured." if self.market_data else "No live market data adapter configured; defaulting to no-edge.",
        }
        if self.market_data is None:
            items = [self._pass(ticker, ["No live market data adapter configured."], "no_adapter") for ticker in universe]
            data_status = "no_adapter"
        else:
            benchmark_candles = self._benchmark_candles()
            items = [self._evaluate_ticker(ticker, mode, benchmark_candles) for ticker in universe]
            data_status = "available"

        items = sorted(items, key=lambda item: item["score"], reverse=True)[:max_candidates]
        for item in items:
            self.recommendations.log(item["ticker"], item["status"], item["score"], item)

        result = {
            "mode": mode,
            "review_only": self.settings.review_only,
            "market_regime": regime,
            "data_provider": provider_name,
            "data_provider_details": provider_details,
            "data_status": data_status,
            "top_candidates": [item for item in items if item["status"] != "PASS"],
            "pass_list": [item for item in items if item["status"] == "PASS"],
            "notes": "Market data adapter active; candidates remain review-only and PASS-first." if self.market_data else "No live market data adapter configured; PASS-first behavior preserved.",
        }
        self.events.log("scan", result)
        return result

    def analyze_ticker(self, ticker: str, mode: str | None = None) -> dict:
        scan = self.run_market_scan(mode or "day_trade", [ticker], 1)
        return self.events.log("ticker_analysis", {"ticker": ticker.upper(), "analysis": scan["top_candidates"] or scan["pass_list"]})

    def watchlist(self) -> dict:
        return {"watchlist": list(self.settings.default_watchlist), "scalp_watchlist": list(self.settings.scalp_watchlist)}

    def _universe_for_mode(self, mode: str, tickers: list[str] | None) -> list[str]:
        raw = tickers or (self.settings.scalp_watchlist if self._is_scalp_mode(mode) else self.settings.default_watchlist)
        universe: list[str] = []
        for ticker in raw:
            symbol = ticker.upper().strip()
            if symbol and symbol not in universe:
                universe.append(symbol)
            if len(universe) >= self.settings.max_scan_universe:
                break
        return universe

    def _evaluate_ticker(self, ticker: str, mode: str, benchmark_candles: list[Candle] | None = None) -> dict:
        quote_provider_failed = False
        candle_provider_failed = False
        try:
            quote = self.market_data.get_quote(ticker) if self.market_data else None
        except Exception:
            quote = None
            quote_provider_failed = True
        try:
            candles = self.market_data.get_candles(ticker, self.settings.market_data_interval, self.settings.market_data_period) if self.market_data else []
        except Exception:
            candles = []
            candle_provider_failed = True
        if (quote is None or quote.price <= 0) and self._candles_can_derive_quote(candles):
            quote = self._quote_from_candles(ticker, candles)

        reasons = self._rejection_reasons(quote, candles)
        if quote_provider_failed and (quote is None or not self._quote_is_derived(quote)):
            reasons.insert(0, "Quote provider request failed safely.")
        if candle_provider_failed and not candles:
            reasons.append("Candle provider request failed safely.")
        if reasons:
            return self._pass(ticker, reasons, "rejected", quote, candles)

        signals = self._signals(quote, candles, mode, benchmark_candles)
        threshold = self._threshold_for_mode(mode)
        if signals["score"] < threshold:
            return self._pass(ticker, [f"Score below {mode} threshold.", "Setup quality is unclear."], "weak_score", quote, candles, signals)

        candidate = {
            "ticker": ticker.upper(),
            "status": "CANDIDATE",
            "score": round(signals["score"], 2),
            "confidence": signals["confidence"],
            "direction": signals["direction"],
            "setup_type": mode,
            "quote_summary": self._quote_summary(quote),
            "candle_summary": self._candle_summary(candles),
            "quality_gates": {
                "stock_setup_quality": "VALID_CANDIDATE",
                "options_chain_quality": "NOT_VALIDATED",
                "execution_quality": "REVIEW_ONLY_NO_EXECUTION",
            },
            "key_signals": signals,
            "risk_notes": self._candidate_risk_notes(quote),
            "reasons": self._candidate_reasons(mode, quote),
            "data_status": "valid",
            "review_only": True,
            "order_allowed": False,
            "postmortem_required": True,
        }
        return self._with_evidence_packet(candidate)

    def _rejection_reasons(self, quote: Quote | None, candles: list[Candle]) -> list[str]:
        reasons: list[str] = []
        if quote is None or quote.price <= 0:
            reasons.append("Quote missing or invalid.")
        elif quote.is_stale or self._is_stale(quote.timestamp):
            reasons.append("Quote data is stale.")

        if not candles:
            reasons.append("Candles missing from market data provider.")
        elif len(candles) < self.settings.min_candle_count:
            reasons.append("Insufficient candle count for conservative review.")
        else:
            if self._is_stale(candles[-1].timestamp):
                reasons.append("Candle data is stale.")
            if any(c.open <= 0 or c.high <= 0 or c.low <= 0 or c.close <= 0 for c in candles):
                reasons.append("Malformed candle OHLC data.")
            if sum(max(c.volume, 0) for c in candles) < self.settings.min_equity_volume:
                reasons.append("Volume/liquidity is below configured floor.")
        return reasons

    def _candles_can_derive_quote(self, candles: list[Candle]) -> bool:
        if len(candles) < max(2, self.settings.min_candle_count):
            return False
        if self._is_stale(candles[-1].timestamp):
            return False
        return all(c.open > 0 and c.high > 0 and c.low > 0 and c.close > 0 for c in candles[-2:])

    def _quote_from_candles(self, ticker: str, candles: list[Candle]) -> Quote:
        latest = candles[-1]
        previous = candles[-2]
        return Quote(
            ticker=ticker.upper(),
            price=latest.close,
            previous_close=previous.close,
            open=latest.open,
            high=latest.high,
            low=latest.low,
            volume=latest.volume,
            timestamp=latest.timestamp,
            provider=f"{latest.provider}_derived_quote",
        )

    def _signals(self, quote: Quote, candles: list[Candle], mode: str = "conservative_review_only", benchmark_candles: list[Candle] | None = None) -> dict:
        closes = [c.close for c in candles]
        volumes = [max(c.volume, 0) for c in candles]
        trend_pct = 0.0 if closes[0] == 0 else (closes[-1] - closes[0]) / closes[0]
        recent_trend_pct = 0.0 if len(closes) < 5 or closes[-5] == 0 else (closes[-1] - closes[-5]) / closes[-5]
        vwap = self._vwap(candles)
        relative_volume, relative_volume_status = self._relative_volume(candles)
        relative_volume_for_score = relative_volume or 0.0
        pct_change = 0.0 if not quote.previous_close or quote.previous_close <= 0 else (quote.price - quote.previous_close) / quote.previous_close
        direction = "long" if trend_pct >= 0 else "short"
        relative_strength = self._relative_strength_context(quote.ticker, trend_pct, recent_trend_pct, benchmark_candles)
        if self._is_scalp_mode(mode):
            score = self._scalp_score(trend_pct, recent_trend_pct, relative_volume_for_score, pct_change, quote.price, vwap, volumes)
        else:
            score = self._conservative_score(trend_pct, recent_trend_pct, relative_volume_for_score, pct_change, quote.price, vwap, volumes)
        score = max(0.0, min(100.0, score))
        threshold = self._threshold_for_mode(mode)
        confidence = "medium" if score >= 80 else "low-medium" if score >= threshold else "low"
        evidence_scorecard = self._evidence_scorecard(
            mode,
            trend_pct,
            recent_trend_pct,
            relative_volume,
            pct_change,
            quote.price,
            vwap,
            volumes,
            direction,
            score,
            self._quote_is_derived(quote),
            relative_strength,
        )
        return {
            "score": score,
            "confidence": confidence,
            "direction": direction,
            "trend_pct": round(trend_pct, 4),
            "recent_trend_pct": round(recent_trend_pct, 4),
            "above_vwap": bool(vwap and quote.price > vwap),
            "below_vwap": bool(vwap and quote.price < vwap),
            "vwap": round(vwap, 4) if vwap else None,
            "relative_volume": round(relative_volume, 2) if relative_volume is not None else None,
            "relative_volume_status": relative_volume_status,
            "pct_change_vs_previous_close": round(pct_change, 4),
            "abs_change_vs_previous_close": round(abs(pct_change), 4),
            "pct_change_source": "prior_candle_close" if self._quote_is_derived(quote) else "provider_previous_close",
            "candle_count": len(candles),
            "scan_profile": "scalp" if self._is_scalp_mode(mode) else "conservative",
            "relative_strength": relative_strength,
            "evidence_scorecard": evidence_scorecard,
        }

    def _conservative_score(self, trend_pct: float, recent_trend_pct: float, relative_volume: float, pct_change: float, price: float, vwap: float | None, volumes: list[int]) -> float:
        score = 0.0
        if trend_pct > 0.015:
            score += 22
        if recent_trend_pct > 0.004:
            score += 18
        if vwap and price > vwap:
            score += 15
        if relative_volume >= 1.2:
            score += 15
        if pct_change > 0:
            score += 10
        if sum(volumes) >= self.settings.min_equity_volume * 2:
            score += 10
        if abs(trend_pct) < 0.004:
            score -= 20
        return score

    def _scalp_score(self, trend_pct: float, recent_trend_pct: float, relative_volume: float, pct_change: float, price: float, vwap: float | None, volumes: list[int]) -> float:
        score = 0.0
        if abs(pct_change) >= self.settings.scalp_min_abs_change_pct:
            score += 20
        if abs(trend_pct) >= 0.008:
            score += 18
        if abs(recent_trend_pct) >= 0.003:
            score += 16
        if relative_volume >= self.settings.scalp_min_relative_volume:
            score += 18
        if vwap and ((trend_pct >= 0 and price > vwap) or (trend_pct < 0 and price < vwap)):
            score += 12
        if sum(volumes) >= self.settings.min_equity_volume * 2:
            score += 10
        if abs(pct_change) < self.settings.scalp_min_abs_change_pct and relative_volume < self.settings.scalp_min_relative_volume:
            score -= 18
        return score

    def _evidence_scorecard(
        self,
        mode: str,
        trend_pct: float,
        recent_trend_pct: float,
        relative_volume: float | None,
        pct_change: float,
        price: float,
        vwap: float | None,
        volumes: list[int],
        direction: str,
        current_score: float,
        quote_derived: bool,
        relative_strength: dict | None = None,
    ) -> dict:
        vwap_aligned = bool(vwap and ((direction == "long" and price > vwap) or (direction == "short" and price < vwap)))
        modules = [
            self._scorecard_module("volume_liquidity", self._volume_evidence_points(relative_volume, volumes), 17, self._volume_evidence_reason(relative_volume)),
            self._scorecard_module("structure_vwap", 18 if vwap_aligned else 5 if vwap else 0, 23, "Direction aligns with VWAP." if vwap_aligned else "VWAP conflict or unavailable."),
            self._scorecard_module("relative_strength_vs_spy", self._relative_strength_points(relative_strength), 14, self._relative_strength_reason(relative_strength)),
            self._scorecard_module("volatility_expansion", self._movement_evidence_points(trend_pct, recent_trend_pct), 10, "Trend/recent-trend expansion proxy."),
            self._scorecard_module("order_flow_or_proxy", self._bar_proxy_points(pct_change, trend_pct), 12, "Bar-pressure proxy; no L2/order-flow data in this build."),
        ]
        penalties = self._scorecard_penalties(mode, relative_volume, pct_change, vwap, direction, price, quote_derived, relative_strength)
        base_score = sum(item["points"] for item in modules)
        penalty_score = min(20.0, sum(item["penalty"] for item in penalties))
        preview_score = max(0.0, min(100.0, base_score - penalty_score))
        return {
            "model": "research_report_v1_preview",
            "active_scanner_score": round(current_score, 2),
            "preview_base_score": round(base_score, 2),
            "preview_penalty_score": round(penalty_score, 2),
            "preview_final_score": round(preview_score, 2),
            "modules": modules,
            "penalties": penalties,
            "missing_or_planned_modules": [
                "catalyst_context",
                "sector_relative_strength",
                "higher_timeframe_context",
                "full_l2_order_flow",
                "options_suitability_until_options_review",
            ],
            "notes": [
                "Preview score is diagnostic only; candidate gating still uses active scanner score.",
                "Missing premium modules are named explicitly so they are not silently treated as known.",
            ],
        }

    def _scorecard_module(self, name: str, points: float, max_points: float, reason: str) -> dict:
        return {"name": name, "points": round(max(0.0, min(max_points, points)), 2), "max_points": max_points, "reason": reason}

    def _volume_evidence_points(self, relative_volume: float | None, volumes: list[int]) -> float:
        points = 0.0
        if relative_volume is None:
            points += 2
        elif relative_volume >= 2.5:
            points += 12
        elif relative_volume >= 1.8:
            points += 9
        elif relative_volume >= self.settings.scalp_min_relative_volume:
            points += 6
        elif relative_volume >= 0.8:
            points += 3
        else:
            points += 1
        if sum(volumes) >= self.settings.min_equity_volume * 2:
            points += 5
        return points

    def _volume_evidence_reason(self, relative_volume: float | None) -> str:
        if relative_volume is None:
            return "RVOL unavailable; participation is unconfirmed."
        if relative_volume >= 2.5:
            return "Strong participation expansion."
        if relative_volume >= self.settings.scalp_min_relative_volume:
            return "Participation clears preferred floor."
        return "Participation is below preferred scalp floor."

    def _movement_evidence_points(self, trend_pct: float, recent_trend_pct: float) -> float:
        points = 0.0
        if abs(trend_pct) >= 0.015:
            points += 5
        elif abs(trend_pct) >= 0.008:
            points += 3
        if abs(recent_trend_pct) >= 0.004:
            points += 5
        elif abs(recent_trend_pct) >= 0.003:
            points += 3
        return points

    def _bar_proxy_points(self, pct_change: float, trend_pct: float) -> float:
        points = 0.0
        if abs(pct_change) >= self.settings.scalp_min_abs_change_pct:
            points += 6
        if abs(trend_pct) >= 0.008:
            points += 4
        return points

    def _relative_strength_points(self, relative_strength: dict | None) -> float:
        if not relative_strength or relative_strength.get("status") != "available":
            return 0.0
        excess = float(relative_strength.get("excess_trend_pct") or 0.0)
        recent_excess = float(relative_strength.get("excess_recent_trend_pct") or 0.0)
        direction = str(relative_strength.get("direction") or "")
        aligned = (direction == "long" and excess > 0 and recent_excess >= 0) or (direction == "short" and excess < 0 and recent_excess <= 0)
        if aligned and abs(excess) >= 0.01:
            return 14.0
        if aligned:
            return 10.0
        if abs(excess) >= 0.004:
            return 5.0
        return 2.0

    def _relative_strength_reason(self, relative_strength: dict | None) -> str:
        if not relative_strength or relative_strength.get("status") != "available":
            return "SPY-relative strength unavailable; sector-relative strength still planned."
        label = relative_strength.get("label") or "neutral"
        return f"SPY-relative strength diagnostic is {label}; sector-relative strength still planned."

    def _scorecard_penalties(self, mode: str, relative_volume: float | None, pct_change: float, vwap: float | None, direction: str, price: float, quote_derived: bool, relative_strength: dict | None = None) -> list[dict]:
        penalties: list[dict] = []
        if self._is_scalp_mode(mode):
            if relative_volume is None:
                penalties.append({"name": "unconfirmed_relative_volume", "penalty": 2.0, "reason": "RVOL is unavailable."})
            elif relative_volume < self.settings.scalp_min_relative_volume:
                penalties.append({"name": "low_relative_volume", "penalty": 3.0, "reason": "RVOL is below preferred scalp floor; keep urgency cautious."})
            if abs(pct_change) < self.settings.scalp_min_abs_change_pct:
                penalties.append({"name": "weak_price_expansion", "penalty": 2.0, "reason": "Move is below preferred scalp expansion threshold."})
        if vwap and ((direction == "long" and price < vwap) or (direction == "short" and price > vwap)):
            penalties.append({"name": "vwap_conflict", "penalty": 6.0, "reason": "Direction conflicts with VWAP state."})
        if quote_derived:
            penalties.append({"name": "quote_derived_from_candles", "penalty": 1.0, "reason": "Quote was derived from candles, not provider quote endpoint."})
        if relative_strength and relative_strength.get("status") == "available":
            label = str(relative_strength.get("label") or "")
            if "lagging" in label:
                penalties.append({"name": "relative_strength_lagging_spy", "penalty": 4.0, "reason": "Ticker is lagging SPY for its current direction."})
        return penalties

    def _benchmark_candles(self) -> list[Candle] | None:
        if not self.market_data:
            return None
        try:
            candles = self.market_data.get_candles("SPY", self.settings.market_data_interval, self.settings.market_data_period)
        except Exception:
            return None
        if len(candles) < self.settings.min_candle_count:
            return None
        if self._is_stale(candles[-1].timestamp):
            return None
        if any(c.open <= 0 or c.high <= 0 or c.low <= 0 or c.close <= 0 for c in candles):
            return None
        return candles

    def _relative_strength_context(self, ticker: str, trend_pct: float, recent_trend_pct: float, benchmark_candles: list[Candle] | None) -> dict:
        if ticker.upper() == "SPY":
            return {"status": "benchmark_self", "benchmark": "SPY", "label": "benchmark_self"}
        if not benchmark_candles or len(benchmark_candles) < 5:
            return {"status": "unavailable", "benchmark": "SPY", "reason": "SPY benchmark candles unavailable."}
        closes = [c.close for c in benchmark_candles if c.close > 0]
        if len(closes) < 5:
            return {"status": "unavailable", "benchmark": "SPY", "reason": "SPY benchmark closes insufficient."}
        benchmark_trend = 0.0 if closes[0] == 0 else (closes[-1] - closes[0]) / closes[0]
        benchmark_recent = 0.0 if closes[-5] == 0 else (closes[-1] - closes[-5]) / closes[-5]
        excess = trend_pct - benchmark_trend
        recent_excess = recent_trend_pct - benchmark_recent
        direction = "long" if trend_pct >= 0 else "short"
        aligned = (direction == "long" and excess > 0 and recent_excess >= 0) or (direction == "short" and excess < 0 and recent_excess <= 0)
        lagging = (direction == "long" and excess < 0) or (direction == "short" and excess > 0)
        label = "leading_spy" if aligned else "lagging_spy" if lagging else "mixed_vs_spy"
        return {
            "status": "available",
            "benchmark": "SPY",
            "direction": direction,
            "benchmark_trend_pct": round(benchmark_trend, 4),
            "benchmark_recent_trend_pct": round(benchmark_recent, 4),
            "excess_trend_pct": round(excess, 4),
            "excess_recent_trend_pct": round(recent_excess, 4),
            "label": label,
            "note": "Diagnostic only until backtested; sector-relative strength remains planned.",
        }

    def _is_scalp_mode(self, mode: str) -> bool:
        return "scalp" in mode.lower() or "mover" in mode.lower()

    def _threshold_for_mode(self, mode: str) -> float:
        return self.settings.scalp_candidate_score_threshold if self._is_scalp_mode(mode) else self.settings.candidate_score_threshold

    def _pass(self, ticker: str, reasons: list[str], data_status: str, quote: Quote | None = None, candles: list[Candle] | None = None, signals: dict | None = None) -> dict:
        item = {
            "ticker": ticker.upper(),
            "status": "PASS",
            "score": round((signals or {}).get("score", 0.0), 2),
            "confidence": "low",
            "direction": "none",
            "setup_type": "PASS",
            "quote_summary": self._quote_summary(quote),
            "candle_summary": self._candle_summary(candles or []),
            "quality_gates": {
                "stock_setup_quality": "PASS",
                "options_chain_quality": "NOT_VALIDATED",
                "execution_quality": "REVIEW_ONLY_NO_EXECUTION",
            },
            "key_signals": signals or {},
            "risk_notes": ["PASS-first behavior: do not force unclear setups."],
            "reasons": reasons,
            "data_status": data_status,
            "review_only": True,
            "order_allowed": False,
            "postmortem_required": True,
        }
        return self._with_evidence_packet(item)

    def _with_evidence_packet(self, item: dict) -> dict:
        signals = item.get("key_signals") if isinstance(item.get("key_signals"), dict) else {}
        quote = item.get("quote_summary") if isinstance(item.get("quote_summary"), dict) else {}
        candles = item.get("candle_summary") if isinstance(item.get("candle_summary"), dict) else {}
        scorecard = signals.get("evidence_scorecard") if isinstance(signals.get("evidence_scorecard"), dict) else {}
        flags = self._evidence_flags(item, quote, candles, signals, scorecard)
        item["evidence_packet"] = {
            "schema_version": "1.0",
            "packet_type": "compact_scan_evidence",
            "build_version": BUILD_VERSION,
            "ticker": item.get("ticker"),
            "status": item.get("status"),
            "score": item.get("score"),
            "direction": item.get("direction"),
            "setup_type": item.get("setup_type"),
            "provider_lineage": {
                "quote_provider": quote.get("provider"),
                "quote_timestamp": quote.get("timestamp"),
                "quote_freshness_status": quote.get("freshness_status"),
                "quote_derived_from_candles": bool(quote.get("derived_from_candles")),
                "candle_provider": candles.get("provider"),
                "candle_last_timestamp": candles.get("last_timestamp"),
                "candle_freshness_status": candles.get("freshness_status"),
                "candle_count": candles.get("count"),
            },
            "data_confidence": self._evidence_confidence(flags, candles),
            "data_flags": flags,
            "missing_or_planned_modules": scorecard.get("missing_or_planned_modules") or [],
            "replay_fields_present": {
                "quote_summary": bool(quote),
                "candle_summary": bool(candles),
                "key_signals": bool(signals),
                "evidence_scorecard": bool(scorecard),
                "quality_gates": bool(item.get("quality_gates")),
            },
            "review_only": True,
            "can_place_order_from_this_mcp": False,
        }
        return item

    def _evidence_flags(self, item: dict, quote: dict, candles: dict, signals: dict, scorecard: dict) -> list[str]:
        flags: list[str] = []
        quote_freshness = str(quote.get("freshness_status") or "")
        candle_freshness = str(candles.get("freshness_status") or "")
        if quote.get("derived_from_candles"):
            flags.append("quote_derived_from_candles")
        if quote_freshness.startswith("STALE"):
            flags.append("quote_stale")
        if candle_freshness.startswith("STALE"):
            flags.append("candles_stale")
        rvol = signals.get("relative_volume")
        if rvol is None and signals:
            flags.append("relative_volume_unavailable")
        elif rvol is not None and float(rvol) < self.settings.scalp_min_relative_volume:
            flags.append("relative_volume_below_preferred_floor")
        if item.get("status") == "PASS":
            flags.append("pass_first_decision")
        missing = scorecard.get("missing_or_planned_modules") or []
        if "catalyst_context" in missing:
            flags.append("catalyst_context_missing")
        if "relative_strength_vs_spy_and_sector" in missing or "relative_strength_vs_spy" in missing:
            flags.append("relative_strength_missing")
        if "sector_relative_strength" in missing:
            flags.append("sector_relative_strength_missing")
        if "full_l2_order_flow" in missing:
            flags.append("l2_order_flow_missing")
        return flags

    def _evidence_confidence(self, flags: list[str], candles: dict) -> dict:
        score = 100
        penalties = {
            "quote_stale": 30,
            "candles_stale": 30,
            "quote_derived_from_candles": 10,
            "relative_volume_unavailable": 12,
            "relative_volume_below_preferred_floor": 6,
            "catalyst_context_missing": 10,
            "relative_strength_missing": 10,
            "sector_relative_strength_missing": 5,
            "l2_order_flow_missing": 5,
        }
        applied = []
        for flag in flags:
            penalty = penalties.get(flag, 0)
            if penalty:
                score -= penalty
                applied.append({"flag": flag, "penalty": penalty})
        if int(candles.get("count") or 0) < 50:
            score -= 10
            applied.append({"flag": "low_candle_count", "penalty": 10})
        score = max(0, min(100, score))
        return {
            "score": score,
            "status": "HIGH" if score >= 80 else "MEDIUM" if score >= 55 else "LOW",
            "penalties": applied,
        }

    def _quote_summary(self, quote: Quote | None) -> dict | None:
        if quote is None:
            return None
        return {
            "ticker": quote.ticker,
            "price": quote.price,
            "previous_close": quote.previous_close,
            "previous_close_source": "prior_candle_close" if self._quote_is_derived(quote) else "provider_previous_close",
            "timestamp": quote.timestamp.isoformat() if quote.timestamp else None,
            "provider": quote.provider,
            "derived_from_candles": self._quote_is_derived(quote),
            "freshness_status": self._freshness_status(quote.timestamp),
        }

    def _candle_summary(self, candles: list[Candle]) -> dict:
        if not candles:
            return {"count": 0}
        return {
            "count": len(candles),
            "first_timestamp": candles[0].timestamp.isoformat(),
            "last_timestamp": candles[-1].timestamp.isoformat(),
            "first_close": candles[0].close,
            "last_close": candles[-1].close,
            "total_volume": sum(c.volume for c in candles),
            "interval": candles[-1].interval,
            "provider": candles[-1].provider,
            "freshness_status": self._freshness_status(candles[-1].timestamp),
        }

    def _vwap(self, candles: list[Candle]) -> float | None:
        total_volume = sum(max(c.volume, 0) for c in candles)
        if total_volume <= 0:
            return None
        return sum(((c.high + c.low + c.close) / 3) * max(c.volume, 0) for c in candles) / total_volume

    def _relative_volume(self, candles: list[Candle]) -> tuple[float | None, str]:
        if len(candles) < 2:
            return None, "unavailable_insufficient_candles"
        latest = candles[-1]
        current_volume = max(latest.volume, 0)
        if current_volume <= 0:
            return None, "unavailable_latest_volume_zero"

        same_time_history = [
            max(candle.volume, 0)
            for candle in candles[:-1]
            if candle.timestamp.date() != latest.timestamp.date()
            and candle.timestamp.hour == latest.timestamp.hour
            and candle.timestamp.minute == latest.timestamp.minute
            and candle.volume > 0
        ]
        if same_time_history:
            baseline = mean(same_time_history)
            if baseline > 0:
                return current_volume / baseline, "same_time_of_day"

        prior_volume = [max(candle.volume, 0) for candle in candles[:-1] if candle.volume > 0]
        if prior_volume:
            baseline = mean(prior_volume)
            if baseline > 0:
                return current_volume / baseline, "rolling_candle_average"
        return None, "unavailable_no_positive_baseline"

    def _is_stale(self, timestamp: datetime | None) -> bool:
        return self._freshness_status(timestamp).startswith("STALE")

    def _quote_is_derived(self, quote: Quote | None) -> bool:
        return bool(quote and quote.provider.endswith("_derived_quote"))

    def _candidate_reasons(self, mode: str, quote: Quote) -> list[str]:
        if self._quote_is_derived(quote):
            return [f"Fresh candle data cleared {mode} threshold; quote was derived from latest candle close."]
        return [f"Fresh quote/candle data cleared {mode} threshold."]

    def _candidate_risk_notes(self, quote: Quote) -> list[str]:
        notes = ["Review-only. No broker execution exists in this MCP.", "Options chain quality is not validated yet."]
        if self._quote_is_derived(quote):
            notes.append("Quote endpoint was unavailable or invalid; previous-close comparison uses prior candle close, not broker quote data.")
        return notes

    def _freshness_status(self, timestamp: datetime | None) -> str:
        if timestamp is None:
            return "STALE_MISSING_TIMESTAMP"
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        timestamp_utc = timestamp.astimezone(UTC)
        if self._market_is_regular_open(now):
            limit_minutes = min(self.settings.max_data_staleness_minutes, self.settings.regular_market_max_staleness_minutes)
            if (now - timestamp_utc).total_seconds() > limit_minutes * 60:
                return "STALE_DURING_REGULAR_MARKET"
            return "FRESH_REGULAR_MARKET"
        last_close = self._latest_regular_close(now)
        if timestamp_utc < last_close - timedelta(minutes=90):
            return "STALE_BEFORE_LAST_REGULAR_SESSION"
        return "LAST_REGULAR_SESSION_ACCEPTED"

    def _market_is_regular_open(self, now: datetime) -> bool:
        eastern = now.astimezone(ZoneInfo("America/New_York"))
        if eastern.weekday() >= 5:
            return False
        return time(9, 30) <= eastern.time() <= time(16, 0)

    def _latest_regular_close(self, now: datetime) -> datetime:
        eastern_zone = ZoneInfo("America/New_York")
        eastern = now.astimezone(eastern_zone)
        close_time = time(16, 0)
        close_date = eastern.date()
        if eastern.weekday() >= 5 or eastern.time() < close_time:
            close_date = close_date - timedelta(days=1)
        while close_date.weekday() >= 5:
            close_date = close_date - timedelta(days=1)
        return datetime.combine(close_date, close_time, tzinfo=eastern_zone).astimezone(UTC)
