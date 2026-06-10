from __future__ import annotations

from collections import Counter
from typing import Any

from app.version import BUILD_VERSION
from app.storage.repositories import EventRepository


class EvidencePacketService:
    def __init__(self, events: EventRepository):
        self.events = events

    def build_packet(self, item: dict[str, Any], source: str = "manual") -> dict[str, Any]:
        packet = self._packet(item, source)
        return self.events.log("evidence_packet", packet)

    def build_packets_from_scan(self, scan_result: dict[str, Any], source: str = "scan_result") -> dict[str, Any]:
        rows = list(scan_result.get("top_candidates") or []) + list(scan_result.get("pass_list") or [])
        packets = [self._packet(row, source) for row in rows]
        payload = {
            "status": "EVIDENCE_PACKETS_READY",
            "build_version": BUILD_VERSION,
            "source": source,
            "packet_count": len(packets),
            "packets": packets,
            "summary": self._summary(packets),
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }
        return self.events.log("evidence_packet_batch", payload)

    def summarize_packets(self, packets: list[dict[str, Any]] | None = None, limit: int = 100) -> dict[str, Any]:
        if packets is None:
            events = self.events.recent("evidence_packet", limit)
            packets = [event["payload"] for event in events if isinstance(event.get("payload"), dict)]
        payload = {
            "status": "EVIDENCE_PACKET_SUMMARY_READY",
            "build_version": BUILD_VERSION,
            "packet_count": len(packets),
            "summary": self._summary(packets),
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }
        return self.events.log("evidence_packet_summary", payload)

    def _packet(self, item: dict[str, Any], source: str) -> dict[str, Any]:
        signals = item.get("key_signals") if isinstance(item.get("key_signals"), dict) else {}
        quote = item.get("quote_summary") if isinstance(item.get("quote_summary"), dict) else {}
        candles = item.get("candle_summary") if isinstance(item.get("candle_summary"), dict) else {}
        scorecard = signals.get("evidence_scorecard") if isinstance(signals.get("evidence_scorecard"), dict) else {}
        quality_gates = item.get("quality_gates") if isinstance(item.get("quality_gates"), dict) else {}
        missing_modules = list(scorecard.get("missing_or_planned_modules") or [])
        data_flags = self._data_flags(item, quote, candles, signals, missing_modules)
        confidence = self._data_confidence(data_flags, quote, candles)
        return {
            "schema_version": "1.0",
            "packet_type": "point_in_time_scan_evidence",
            "build_version": BUILD_VERSION,
            "source": source,
            "ticker": item.get("ticker"),
            "decision": {
                "status": item.get("status"),
                "score": item.get("score"),
                "confidence": item.get("confidence"),
                "direction": item.get("direction"),
                "setup_type": item.get("setup_type"),
                "reasons": item.get("reasons") or [],
            },
            "provider_lineage": {
                "quote_provider": quote.get("provider"),
                "quote_timestamp": quote.get("timestamp"),
                "quote_freshness_status": quote.get("freshness_status"),
                "quote_derived_from_candles": bool(quote.get("derived_from_candles")),
                "candle_provider": candles.get("provider"),
                "candle_first_timestamp": candles.get("first_timestamp"),
                "candle_last_timestamp": candles.get("last_timestamp"),
                "candle_freshness_status": candles.get("freshness_status"),
                "candle_count": candles.get("count"),
                "interval": candles.get("interval"),
            },
            "quality_gates": quality_gates,
            "feature_snapshot": {
                "trend_pct": signals.get("trend_pct"),
                "recent_trend_pct": signals.get("recent_trend_pct"),
                "pct_change_vs_previous_close": signals.get("pct_change_vs_previous_close"),
                "relative_volume": signals.get("relative_volume"),
                "relative_volume_status": signals.get("relative_volume_status"),
                "above_vwap": signals.get("above_vwap"),
                "below_vwap": signals.get("below_vwap"),
                "vwap": signals.get("vwap"),
                "relative_strength": signals.get("relative_strength"),
                "scan_profile": signals.get("scan_profile"),
            },
            "evidence_scorecard": scorecard,
            "data_confidence": confidence,
            "data_flags": data_flags,
            "missing_or_planned_modules": missing_modules,
            "options_snapshot_status": self._options_snapshot_status(item),
            "learning_use": {
                "can_train_from_packet": confidence["status"] != "LOW",
                "needs_blame_attribution": True,
                "do_not_auto_apply_learning": True,
            },
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }

    def _data_flags(self, item: dict[str, Any], quote: dict[str, Any], candles: dict[str, Any], signals: dict[str, Any], missing_modules: list[str]) -> list[str]:
        flags: list[str] = []
        quote_freshness = str(quote.get("freshness_status") or "")
        candle_freshness = str(candles.get("freshness_status") or "")
        if quote.get("derived_from_candles"):
            flags.append("quote_derived_from_candles")
        if quote_freshness.startswith("STALE"):
            flags.append("quote_stale")
        if candle_freshness.startswith("STALE"):
            flags.append("candles_stale")
        if signals.get("relative_volume") is None:
            flags.append("relative_volume_unavailable")
        elif self._float(signals.get("relative_volume")) is not None and float(signals.get("relative_volume")) < 1.15:
            flags.append("relative_volume_below_preferred_floor")
        if item.get("status") == "PASS":
            flags.append("pass_first_decision")
        if "catalyst_context" in missing_modules:
            flags.append("catalyst_context_missing")
        if "relative_strength_vs_spy_and_sector" in missing_modules or "relative_strength" in missing_modules or "relative_strength_vs_spy" in missing_modules:
            flags.append("relative_strength_missing")
        if "sector_relative_strength" in missing_modules:
            flags.append("sector_relative_strength_missing")
        if "full_l2_order_flow" in missing_modules:
            flags.append("l2_order_flow_missing")
        return flags

    def _data_confidence(self, data_flags: list[str], quote: dict[str, Any], candles: dict[str, Any]) -> dict[str, Any]:
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
        for flag in data_flags:
            penalty = penalties.get(flag, 0)
            if penalty:
                score -= penalty
                applied.append({"flag": flag, "penalty": penalty})
        candle_count = self._int(candles.get("count")) or 0
        if candle_count < 50:
            score -= 10
            applied.append({"flag": "low_candle_count", "penalty": 10})
        status = "HIGH" if score >= 80 else "MEDIUM" if score >= 55 else "LOW"
        return {
            "score": max(0, min(100, score)),
            "status": status,
            "penalties": applied,
            "note": "Data confidence is an audit aid, not a trade signal.",
        }

    def _options_snapshot_status(self, item: dict[str, Any]) -> dict[str, Any]:
        options = item.get("options_chain_validation") or {}
        small = item.get("small_account_review") or {}
        if options or small:
            return {
                "options_chain_status": options.get("status"),
                "small_account_status": small.get("status"),
                "selected_contract_present": bool(small.get("selected_contract")),
            }
        quality = item.get("quality_gates") if isinstance(item.get("quality_gates"), dict) else {}
        return {
            "options_chain_status": quality.get("options_chain_quality", "NOT_VALIDATED"),
            "small_account_status": "NOT_REVIEWED",
            "selected_contract_present": False,
        }

    def _summary(self, packets: list[dict[str, Any]]) -> dict[str, Any]:
        statuses = Counter(str((packet.get("decision") or {}).get("status")) for packet in packets)
        flags = Counter(flag for packet in packets for flag in packet.get("data_flags", []))
        confidence = Counter(str((packet.get("data_confidence") or {}).get("status")) for packet in packets)
        missing = Counter(module for packet in packets for module in packet.get("missing_or_planned_modules", []))
        return {
            "decision_counts": dict(statuses),
            "data_confidence_counts": dict(confidence),
            "top_data_flags": dict(flags.most_common(12)),
            "missing_module_counts": dict(missing.most_common(12)),
            "recommendation": self._recommendation(flags, confidence),
        }

    def _recommendation(self, flags: Counter, confidence: Counter) -> str:
        if confidence.get("LOW", 0):
            return "Do not tune strategy from LOW-confidence packets; fix data completeness first."
        if flags.get("relative_strength_missing", 0) or flags.get("sector_relative_strength_missing", 0) or flags.get("catalyst_context_missing", 0):
            return "Next accuracy work should add sector-relative strength and catalyst context before adding more chart patterns."
        return "Evidence packets are usable for review learning, with manual backtest approval still required."

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
