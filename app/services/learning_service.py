from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
from statistics import mean
from typing import Any

from app.storage.repositories import EventRepository


class LearningService:
    """Turns review outcomes into research lessons without changing live rules."""

    def __init__(self, events: EventRepository):
        self.events = events

    def log_research_snapshot(self, snapshot: dict[str, Any]) -> dict:
        payload = {
            "snapshot_id": snapshot.get("snapshot_id") or self._snapshot_id(snapshot),
            "snapshot_type": snapshot.get("snapshot_type") or self._snapshot_type(snapshot),
            "ticker": self._ticker(snapshot),
            "status": snapshot.get("status"),
            "captured_at": snapshot.get("captured_at") or datetime.now(UTC).isoformat(),
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
            "raw_snapshot": snapshot,
            "notes": "Research memory only. This does not approve, place, modify, or cancel orders.",
        }
        return self.events.log("research_snapshot", payload)

    def classify_review_outcome(
        self,
        snapshot: dict[str, Any],
        outcome: dict[str, Any],
        help_threshold: float = 0.003,
        missed_move_threshold: float = 0.006,
    ) -> dict:
        summary = self._snapshot_summary(snapshot)
        outcome_summary = self._outcome_summary(outcome)
        directional_return = outcome_summary["directional_return"]
        mfe = outcome_summary["max_favorable_excursion"]
        mae = outcome_summary["max_adverse_excursion"]

        if directional_return is None and mfe is None:
            classification = "UNCLASSIFIED_OUTCOME_UNAVAILABLE"
            reason = "Outcome did not include a directional return or favorable excursion."
        elif summary["passed_full_review"]:
            classification, reason = self._classify_passed_review(directional_return, mfe, mae, help_threshold)
        elif summary["stock_candidate"] and not summary["small_account_acceptable"]:
            classification, reason = self._classify_blocked_candidate(directional_return, mfe, missed_move_threshold)
        elif summary["pass_or_rejected"]:
            classification, reason = self._classify_pass_or_reject(directional_return, mfe, missed_move_threshold)
        else:
            classification = "FLAT_NO_CLEAR_LESSON"
            reason = "Snapshot did not map cleanly to a passed review or rejected/pass item."

        payload = {
            "ticker": summary["ticker"],
            "classification": classification,
            "reason": reason,
            "direction": summary["direction"],
            "status": summary["status"],
            "stock_score": summary["stock_score"],
            "priority_score": summary["priority_score"],
            "lesson_tags": self._lesson_tags(summary, snapshot),
            "snapshot_summary": summary,
            "outcome_summary": outcome_summary,
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
            "notes": "Learning label only. Do not treat this as an execution signal.",
        }
        return self.events.log("learning_outcome_classification", payload)

    def summarize_learning(self, classifications: list[dict[str, Any]] | None = None, limit: int = 100) -> dict:
        items = classifications or [
            event["payload"]
            for event in self.events.recent("learning_outcome_classification", limit)
            if isinstance(event.get("payload"), dict)
        ]
        usable = [item for item in items if item.get("classification")]
        counter = Counter(str(item.get("classification")) for item in usable)
        tag_counter: Counter[str] = Counter()
        returns = []
        for item in usable:
            tag_counter.update(str(tag) for tag in item.get("lesson_tags", []))
            outcome = item.get("outcome_summary") or {}
            value = outcome.get("directional_return")
            if value is not None:
                returns.append(float(value))
        payload = {
            "sample_size": len(usable),
            "classification_counts": dict(counter),
            "top_lesson_tags": dict(tag_counter.most_common(10)),
            "average_directional_return": round(mean(returns), 5) if returns else None,
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
            "notes": "Research summary only. Rule changes still require human review and more evidence.",
        }
        return self.events.log("learning_summary", payload)

    def generate_rule_proposals(
        self,
        classifications: list[dict[str, Any]] | None = None,
        min_samples: int = 3,
        limit: int = 100,
    ) -> dict:
        items = classifications or [
            event["payload"]
            for event in self.events.recent("learning_outcome_classification", limit)
            if isinstance(event.get("payload"), dict)
        ]
        proposals = []
        tag_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            for tag in item.get("lesson_tags", []):
                tag_groups[str(tag)].append(item)

        for tag, tagged_items in sorted(tag_groups.items()):
            if len(tagged_items) < min_samples:
                continue
            proposal = self._proposal_for_tag(tag, tagged_items)
            if proposal:
                proposals.append(proposal)

        high_signal = [
            item
            for item in items
            if item.get("classification") in {"FALSE_POSITIVE", "MISSED_MOVE", "BAD_CONTRACT_OR_TOO_STRICT"}
        ]
        payload = {
            "status": "RULE_PROPOSALS_READY" if proposals else "NO_RULE_PROPOSAL_YET",
            "min_samples_required": min_samples,
            "sample_size": len(items),
            "high_signal_mistakes": len(high_signal),
            "proposals": proposals,
            "do_not_auto_apply": True,
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
            "notes": "Proposals are hypotheses. Backtest before changing active gates.",
        }
        return self.events.log("learning_rule_proposals", payload)

    def _classify_passed_review(
        self,
        directional_return: float | None,
        mfe: float | None,
        mae: float | None,
        help_threshold: float,
    ) -> tuple[str, str]:
        if directional_return is not None and directional_return <= -help_threshold:
            return "FALSE_POSITIVE", "The review passed, but the later directional return was negative."
        if mae is not None and mae <= -(help_threshold * 2):
            return "FALSE_POSITIVE", "The review passed, but adverse excursion was large enough to flag risk."
        if directional_return is not None and directional_return >= help_threshold:
            return "GOOD_SIGNAL", "The review passed and later directional return was positive."
        if mfe is not None and mfe >= help_threshold * 2:
            return "EARLY_MOVE_THEN_FADE", "The setup had a favorable window but did not hold cleanly."
        return "FLAT_NO_CLEAR_LESSON", "The review passed, but price did not move enough to teach a strong lesson."

    def _classify_blocked_candidate(
        self,
        directional_return: float | None,
        mfe: float | None,
        missed_move_threshold: float,
    ) -> tuple[str, str]:
        if mfe is not None and mfe >= missed_move_threshold:
            return "BAD_CONTRACT_OR_TOO_STRICT", "The stock setup moved favorably after the options/small-account gate blocked it."
        if directional_return is not None and directional_return <= -missed_move_threshold / 2:
            return "GOOD_BLOCK", "The blocked candidate later moved against the setup."
        return "GOOD_CAUTION", "The block did not obviously cost a strong move."

    def _classify_pass_or_reject(
        self,
        directional_return: float | None,
        mfe: float | None,
        missed_move_threshold: float,
    ) -> tuple[str, str]:
        if mfe is not None and mfe >= missed_move_threshold:
            return "MISSED_MOVE", "The pass/reject item later had enough favorable excursion to study."
        if directional_return is not None and directional_return <= missed_move_threshold / 2:
            return "GOOD_PASS", "The pass/reject item did not later prove itself."
        return "FLAT_NO_CLEAR_LESSON", "The pass/reject item stayed too flat to teach a strong lesson."

    def _proposal_for_tag(self, tag: str, items: list[dict[str, Any]]) -> dict | None:
        counts = Counter(item.get("classification") for item in items)
        false_positive_rate = counts["FALSE_POSITIVE"] / len(items)
        missed_rate = (counts["MISSED_MOVE"] + counts["BAD_CONTRACT_OR_TOO_STRICT"]) / len(items)
        average_return = self._average_return(items)
        if tag == "wide_spread" and false_positive_rate >= 0.5:
            action = "tighten_spread_penalty"
            thesis = "Wide-spread contracts are repeatedly showing poor follow-through."
        elif tag == "low_relative_volume" and false_positive_rate >= 0.5:
            action = "downgrade_low_rvol_priority"
            thesis = "Low-RVOL reviews are repeatedly failing after entry review."
        elif tag == "low_relative_volume" and missed_rate >= 0.5:
            action = "keep_low_rvol_as_watch_not_reject"
            thesis = "Low RVOL is still producing missed moves, so it should warn rather than hard-reject."
        elif tag == "vwap_conflict" and false_positive_rate >= 0.34:
            action = "hard_block_vwap_conflict"
            thesis = "VWAP-conflict setups are failing often enough to stay blocked."
        elif tag == "one_dte" and false_positive_rate >= 0.34:
            action = "keep_1dte_exceptional_only"
            thesis = "1DTE remains too fragile unless every other gate is exceptional."
        elif tag in {"option_chain_gap", "no_small_account_contract"} and missed_rate >= 0.5:
            action = "improve_contract_discovery_or_broker_snapshot"
            thesis = "The stock read worked, but contract discovery blocked the review."
        elif tag in {"quote_issue", "stale_data"} and missed_rate >= 0.5:
            action = "improve_data_fallback_before_rejecting"
            thesis = "Data quality caused passes that later moved; improve validation/fallback."
        else:
            return None
        confidence = "medium" if len(items) >= 5 else "low"
        return {
            "tag": tag,
            "action": action,
            "thesis": thesis,
            "sample_size": len(items),
            "classification_counts": dict(counts),
            "average_directional_return": average_return,
            "confidence": confidence,
            "next_test": "Backtest this proposal before changing active scan gates.",
        }

    def _snapshot_summary(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        stock = snapshot.get("stock_setup") if isinstance(snapshot.get("stock_setup"), dict) else snapshot
        options = snapshot.get("options_chain_validation") or {}
        small = snapshot.get("small_account_review") or {}
        quality = stock.get("quality_gates") or snapshot.get("quality_gates") or {}
        status = str(snapshot.get("status") or stock.get("status") or "")
        small_status = str(small.get("status") or "")
        option_status = str(options.get("status") or "")
        return {
            "ticker": self._ticker(snapshot),
            "status": status,
            "direction": self._normalize_direction(stock.get("direction") or snapshot.get("direction")),
            "stock_score": self._float(stock.get("score")),
            "priority_score": self._float(small.get("priority_score")),
            "stock_candidate": stock.get("status") == "CANDIDATE" or quality.get("stock_setup_quality") == "VALID_CANDIDATE",
            "passed_full_review": status == "REVIEW_ONLY_OPTIONS_READY" or small_status == "SMALL_ACCOUNT_SCALP_ACCEPTABLE",
            "small_account_acceptable": small_status == "SMALL_ACCOUNT_SCALP_ACCEPTABLE",
            "option_chain_acceptable": option_status == "OPTIONS_CHAIN_ACCEPTABLE",
            "pass_or_rejected": status in {"PASS", "NO_TRADE_PLAN"} or stock.get("status") == "PASS",
            "reasons": self._strings(snapshot.get("reasons")) + self._strings(stock.get("reasons")),
            "warnings": self._strings(snapshot.get("warnings")) + self._strings(small.get("warnings")),
            "signals": stock.get("key_signals") or {},
        }

    def _outcome_summary(self, outcome: dict[str, Any]) -> dict[str, Any]:
        horizon_returns = outcome.get("horizon_returns") if isinstance(outcome.get("horizon_returns"), dict) else {}
        directional_return = self._float(outcome.get("current_return_pct"))
        if directional_return is None:
            directional_return = self._first_number(horizon_returns.values())
        return {
            "verdict": outcome.get("verdict"),
            "directional_return": directional_return,
            "horizon_returns": horizon_returns,
            "max_favorable_excursion": self._float(outcome.get("max_favorable_excursion")),
            "max_adverse_excursion": self._float(outcome.get("max_adverse_excursion")),
            "outcome_window_status": outcome.get("outcome_window_status"),
        }

    def _lesson_tags(self, summary: dict[str, Any], snapshot: dict[str, Any]) -> list[str]:
        joined = " ".join(summary["warnings"] + summary["reasons"]).lower()
        tags = set()
        signals = summary.get("signals") or {}
        rvol = self._float(signals.get("relative_volume"))
        if rvol is None:
            tags.add("rvol_unavailable")
        elif rvol < 1.15:
            tags.add("low_relative_volume")
        if "spread" in joined:
            tags.add("wide_spread")
        if "1dte" in joined or "1 dte" in joined:
            tags.add("one_dte")
        if "vwap" in joined and "conflict" in joined:
            tags.add("vwap_conflict")
        if "max loss" in joined:
            tags.add("max_loss")
        if "quote" in joined:
            tags.add("quote_issue")
        if "stale" in joined:
            tags.add("stale_data")
        if "no acceptable small-account contract" in joined or "no small" in joined:
            tags.add("no_small_account_contract")
        if summary.get("stock_candidate") and not summary.get("option_chain_acceptable"):
            tags.add("option_chain_gap")
        if (snapshot.get("quote_summary") or {}).get("derived_from_candles"):
            tags.add("quote_derived_from_candles")
        return sorted(tags)

    def _ticker(self, snapshot: dict[str, Any]) -> str:
        stock = snapshot.get("stock_setup") if isinstance(snapshot.get("stock_setup"), dict) else {}
        return str(snapshot.get("ticker") or stock.get("ticker") or "UNKNOWN").upper()

    def _snapshot_type(self, snapshot: dict[str, Any]) -> str:
        if "top_candidates" in snapshot or "pass_list" in snapshot:
            return "scan"
        if "options_chain_validation" in snapshot or "small_account_review" in snapshot:
            return "options_review"
        return "manual_snapshot"

    def _snapshot_id(self, snapshot: dict[str, Any]) -> str:
        ticker = self._ticker(snapshot)
        status = snapshot.get("status") or self._snapshot_type(snapshot)
        return f"{ticker}-{status}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"

    def _normalize_direction(self, value: Any) -> str | None:
        raw = str(value or "").lower()
        if raw in {"put", "puts", "short", "bearish"}:
            return "short"
        if raw in {"call", "calls", "long", "bullish"}:
            return "long"
        return None

    def _strings(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        return [str(value)]

    def _float(self, value: Any) -> float | None:
        try:
            return None if value is None or value != value else float(value)
        except Exception:
            return None

    def _first_number(self, values: Any) -> float | None:
        for value in values:
            number = self._float(value)
            if number is not None:
                return number
        return None

    def _average_return(self, items: list[dict[str, Any]]) -> float | None:
        returns = []
        for item in items:
            outcome = item.get("outcome_summary") or {}
            value = self._float(outcome.get("directional_return"))
            if value is not None:
                returns.append(value)
        return round(mean(returns), 5) if returns else None
