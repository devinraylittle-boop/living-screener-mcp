from __future__ import annotations

from typing import Any

from app.storage.repositories import EventRepository


class PreMoveBlueprintService:
    """Research-backed blueprint for the next scoring architecture."""

    def __init__(self, events: EventRepository):
        self.events = events

    def blueprint(self) -> dict[str, Any]:
        payload = {
            "status": "PREMOVE_BLUEPRINT_READY",
            "mission": "Detect measurable pre-move state changes, not magic indicators.",
            "version": "research_report_v1",
            "primary_edges": [
                {"edge": "stocks_in_play_orb", "proxy": "catalyst flag plus same-time RVOL plus opening-range acceptance", "horizon": "intraday", "evidence": "moderate", "implementation_priority": 1},
                {"edge": "vwap_state_with_demand_imbalance", "proxy": "price/VWAP alignment, VWAP slope, reclaim/reject behavior, volume acceleration", "horizon": "intraday", "evidence": "moderate", "implementation_priority": 2},
                {"edge": "relative_strength_momentum", "proxy": "excess return versus SPY and sector over 5m/15m/daily windows", "horizon": "intraday_and_swing", "evidence": "strong", "implementation_priority": 3},
                {"edge": "compression_to_expansion", "proxy": "low ATR/BB-width/inside-bar state resolving through a decision level with participation", "horizon": "intraday_and_swing", "evidence": "plausible_to_moderate", "implementation_priority": 4},
                {"edge": "earnings_surprise_post_event_drift", "proxy": "event flag, gap acceptance, post-open hold above/below event VWAP", "horizon": "swing_and_intraday_follow_through", "evidence": "strong", "implementation_priority": 5},
                {"edge": "order_flow_imbalance_near_levels", "proxy": "queue imbalance, OFI z-score, CVD near OR/PMH/PML/HOD/LOD", "horizon": "ultra_short_intraday", "evidence": "moderate_but_perishable", "implementation_priority": 6, "requires_premium_data": True},
            ],
            "thresholds": {
                "strong_alert": "75+",
                "watchlist": "60-74",
                "passive_track": "45-59",
                "ignore": "<45",
                "note": "Thresholds are starting points for walk-forward testing, not permanent constants.",
            },
            "score_policy": {
                "formula": "final_score = clip(base_evidence_score - false_positive_penalty_score, 0, 100)",
                "separate_scores_required": ["bull_score", "bear_score", "expansion_score"],
                "do_not_auto_apply_learning": True,
            },
            "safety": self._safety(),
        }
        return self.events.log("premove_blueprint", payload)

    def feature_registry(self) -> dict[str, Any]:
        payload = {
            "status": "FEATURE_REGISTRY_READY",
            "positive_modules_total_points": 100,
            "positive_modules": [
                {"name": "catalyst_context", "max_points": 15, "features": ["earnings/news/event flag", "gap acceptance", "event-anchored VWAP"], "current_data_status": "partial_or_missing"},
                {"name": "volume_liquidity", "max_points": 17, "features": ["same-time RVOL", "opening RVOL", "volume acceleration", "dollar volume"], "current_data_status": "available_from_intraday_bars"},
                {"name": "structure_vwap", "max_points": 23, "features": ["VWAP state", "VWAP reclaim/reject", "ORB acceptance", "breakout candle quality"], "current_data_status": "partially_available"},
                {"name": "relative_strength", "max_points": 14, "features": ["excess return versus SPY", "excess return versus sector ETF"], "current_data_status": "spy_available_sector_planned"},
                {"name": "volatility_expansion", "max_points": 10, "features": ["ATR/range expansion", "compression break", "close location"], "current_data_status": "partially_available"},
                {"name": "order_flow_or_proxy", "max_points": 12, "features": ["queue imbalance", "OFI", "CVD", "bar-pressure fallback"], "current_data_status": "proxy_only_without_l2"},
                {"name": "higher_timeframe_context", "max_points": 4, "features": ["daily/weekly trend", "distance to major levels"], "current_data_status": "planned"},
                {"name": "options_suitability", "max_points": 5, "features": ["chain grade", "IV rank", "OI/volume/spread quality"], "current_data_status": "available_during_options_review_only"},
            ],
            "false_positive_penalties": [
                {"name": "wide_spread", "max_penalty": 6},
                {"name": "thin_underlying_liquidity", "max_penalty": 5},
                {"name": "thin_option_chain", "max_penalty": 8},
                {"name": "chasing_extension", "max_penalty": 5},
                {"name": "breakout_into_supply_or_support", "max_penalty": 4},
                {"name": "weak_breakout_candle", "max_penalty": 4},
                {"name": "midday_dead_zone", "max_penalty": 3},
                {"name": "repeated_failed_tests", "max_penalty": 4},
                {"name": "unconfirmed_market_context", "max_penalty": 4},
                {"name": "near_binary_event_risk", "max_penalty": 8},
            ],
            "premium_data_needed_for_full_strength": [
                "OPRA consolidated options quotes/trades",
                "CTA/UTP SIP or equivalent L1 equities feed",
                "sector benchmark bars",
                "full depth L2/order book for queue imbalance",
                "point-in-time float and borrow/short-interest context",
                "reliable event/news/corporate-action feed",
            ],
            "safety": self._safety(),
        }
        return self.events.log("feature_registry", payload)

    def scoring_model(self) -> dict[str, Any]:
        payload = {
            "status": "SCORING_MODEL_READY",
            "model": "rules_first_modular_score_with_penalty_overlay",
            "formula": {
                "base_score": "sum(positive_evidence_modules)",
                "penalty_score": "min(sum(false_positive_penalties), 20)",
                "final_score": "clip(base_score - penalty_score, 0, 100)",
            },
            "action_bands": [
                {"band": "strong_alert", "score": "75+", "meaning": "Review immediately; still requires options/liquidity gates."},
                {"band": "watchlist", "score": "60-74", "meaning": "Track; needs improvement or cleaner confirmation."},
                {"band": "passive_track", "score": "45-59", "meaning": "Study only; do not advance to options."},
                {"band": "ignore", "score": "<45", "meaning": "No edge."},
            ],
            "options_mapping": [
                {"condition": "directional_score >= 80 and expansion_score >= 60 and IV rank < 35 and chain grade A/B", "structure": "long_call_or_put"},
                {"condition": "directional_score >= 75 and IV rank 35-70 and chain grade A/B", "structure": "debit_vertical"},
                {"condition": "directional_score 65-79 and IV rank > 70 and chain grade A/B", "structure": "calendar_or_diagonal_review"},
                {"condition": "direction unclear but expansion_score >= 75 and IV rank low", "structure": "long_straddle_or_strangle_review"},
            ],
            "validation_tests_required": [
                "point-in-time feature calculation",
                "no lookahead bias",
                "alert precision by setup type",
                "missed-move recall",
                "MFE/MAE by horizon",
                "spread and slippage stress tests",
                "walk-forward testing",
                "module ablation",
            ],
            "safety": self._safety(),
        }
        return self.events.log("scoring_model", payload)

    def explain_candidate_score(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        stock = snapshot.get("stock_setup") if isinstance(snapshot.get("stock_setup"), dict) else snapshot
        signals = stock.get("key_signals") if isinstance(stock.get("key_signals"), dict) else {}
        current_score = self._float(stock.get("score")) or self._float(signals.get("score")) or 0.0
        rvol = self._float(signals.get("relative_volume"))
        direction = str(stock.get("direction") or signals.get("direction") or "none").lower()
        above_vwap = bool(signals.get("above_vwap"))
        below_vwap = bool(signals.get("below_vwap"))
        modules = [
            self._module("volume_liquidity", self._volume_points(rvol), 17, self._volume_reason(rvol)),
            self._module("structure_vwap", self._vwap_points(direction, above_vwap, below_vwap), 23, self._vwap_reason(direction, above_vwap, below_vwap)),
            self._module("volatility_expansion", self._movement_points(signals), 10, "Trend/recent-trend movement proxy from candle data."),
            self._module("order_flow_or_proxy", self._bar_proxy_points(signals), 12, "Bar-pressure proxy only; no L2/order-flow feed present."),
            self._module("options_suitability", self._options_points(snapshot), 5, "Uses options gate only when an options review snapshot is supplied."),
        ]
        missing = ["catalyst_context", "sector_relative_strength", "higher_timeframe_context"]
        penalty_items = self._penalties(snapshot, signals, rvol, direction, above_vwap, below_vwap)
        base = sum(item["points"] for item in modules)
        penalty = min(sum(item["penalty"] for item in penalty_items), 20.0)
        final = max(0.0, min(100.0, base - penalty))
        payload = {
            "status": "SCORE_EXPLANATION_READY",
            "ticker": stock.get("ticker") or snapshot.get("ticker"),
            "current_scanner_score": round(current_score, 2),
            "research_preview_score": {
                "base_score": round(base, 2),
                "penalty_score": round(penalty, 2),
                "final_score": round(final, 2),
                "note": "Preview score is diagnostic only until backtested; live gates still use the active scanner score.",
            },
            "available_modules": modules,
            "missing_or_planned_modules": missing,
            "penalties": penalty_items,
            "learning_focus": self._learning_focus(penalty_items, missing),
            "safety": self._safety(),
        }
        return self.events.log("score_explanation", payload)

    def _module(self, name: str, points: float, max_points: float, reason: str) -> dict[str, Any]:
        return {"name": name, "points": round(max(0.0, min(max_points, points)), 2), "max_points": max_points, "reason": reason}

    def _volume_points(self, rvol: float | None) -> float:
        if rvol is None:
            return 3.0
        if rvol >= 2.5:
            return 17.0
        if rvol >= 1.8:
            return 13.0
        if rvol >= 1.15:
            return 9.0
        if rvol >= 0.8:
            return 5.0
        return 2.0

    def _volume_reason(self, rvol: float | None) -> str:
        if rvol is None:
            return "RVOL unavailable; urgency unconfirmed."
        if rvol >= 2.5:
            return "Strong same/proxy relative participation."
        if rvol >= 1.15:
            return "Participation is acceptable but not elite."
        return "Relative volume is weak; this is a caution flag, not automatic proof of failure."

    def _vwap_points(self, direction: str, above_vwap: bool, below_vwap: bool) -> float:
        if direction == "long" and above_vwap:
            return 18.0
        if direction == "short" and below_vwap:
            return 18.0
        if direction in {"long", "short"} and (above_vwap or below_vwap):
            return 5.0
        return 0.0

    def _vwap_reason(self, direction: str, above_vwap: bool, below_vwap: bool) -> str:
        if direction == "long" and above_vwap:
            return "Long direction aligns with above-VWAP state."
        if direction == "short" and below_vwap:
            return "Short direction aligns with below-VWAP state."
        if direction in {"long", "short"} and (above_vwap or below_vwap):
            return "Direction conflicts with VWAP state."
        return "VWAP state unavailable or direction unclear."

    def _movement_points(self, signals: dict[str, Any]) -> float:
        trend = abs(self._float(signals.get("trend_pct")) or 0.0)
        recent = abs(self._float(signals.get("recent_trend_pct")) or 0.0)
        points = 0.0
        if trend >= 0.015:
            points += 5
        elif trend >= 0.008:
            points += 3
        if recent >= 0.004:
            points += 5
        elif recent >= 0.003:
            points += 3
        return points

    def _bar_proxy_points(self, signals: dict[str, Any]) -> float:
        pct_change = abs(self._float(signals.get("pct_change_vs_previous_close")) or 0.0)
        if pct_change >= 0.025:
            return 9.0
        if pct_change >= 0.006:
            return 6.0
        return 2.0

    def _options_points(self, snapshot: dict[str, Any]) -> float:
        options = snapshot.get("options_chain_validation") or {}
        small = snapshot.get("small_account_review") or {}
        if options.get("status") == "OPTIONS_CHAIN_ACCEPTABLE" and small.get("status") == "SMALL_ACCOUNT_SCALP_ACCEPTABLE":
            return 5.0
        if options.get("status") == "OPTIONS_CHAIN_ACCEPTABLE":
            return 3.0
        return 0.0

    def _penalties(self, snapshot: dict[str, Any], signals: dict[str, Any], rvol: float | None, direction: str, above_vwap: bool, below_vwap: bool) -> list[dict[str, Any]]:
        penalties: list[dict[str, Any]] = []
        warnings = " ".join(str(item) for item in (snapshot.get("warnings") or (snapshot.get("small_account_review") or {}).get("warnings") or [])).lower()
        if "spread" in warnings:
            penalties.append({"name": "wide_option_spread", "penalty": 4.0, "reason": "Options review warned that spread is wider than preferred."})
        if rvol is None:
            penalties.append({"name": "unconfirmed_participation", "penalty": 2.0, "reason": "RVOL is unavailable."})
        elif rvol < 1.15:
            penalties.append({"name": "low_relative_volume", "penalty": 3.0, "reason": "Participation is below preferred scalp floor."})
        if (direction == "long" and below_vwap) or (direction == "short" and above_vwap):
            penalties.append({"name": "vwap_conflict", "penalty": 6.0, "reason": "Direction conflicts with VWAP state."})
        if abs(self._float(signals.get("pct_change_vs_previous_close")) or 0.0) < 0.006:
            penalties.append({"name": "weak_expansion", "penalty": 2.0, "reason": "Move is below scalp expansion preference."})
        return penalties

    def _learning_focus(self, penalties: list[dict[str, Any]], missing: list[str]) -> list[str]:
        focus = [f"Track outcomes where {item['name']} was present." for item in penalties]
        focus.extend(f"Add/backtest {name} module before giving it live weight." for name in missing)
        return focus[:8]

    def _float(self, value: Any) -> float | None:
        try:
            return None if value is None or value != value else float(value)
        except Exception:
            return None

    def _safety(self) -> dict[str, bool]:
        return {
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
            "do_not_auto_apply_learning": True,
        }
