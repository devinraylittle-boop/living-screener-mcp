from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any

from app.storage.repositories import EventRepository


class SetupMemoryService:
    """Builds review fingerprints and compares them with recent logged lessons."""

    def __init__(self, events: EventRepository):
        self.events = events

    def build_fingerprint(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        stock = snapshot.get("stock_setup") if isinstance(snapshot.get("stock_setup"), dict) else snapshot
        signals = stock.get("key_signals") if isinstance(stock.get("key_signals"), dict) else snapshot.get("key_signals") or {}
        small = snapshot.get("small_account_review") if isinstance(snapshot.get("small_account_review"), dict) else {}
        selected = small.get("selected_contract") if isinstance(small.get("selected_contract"), dict) else {}
        friction = small.get("friction_adjusted_review") if isinstance(small.get("friction_adjusted_review"), dict) else {}
        relative_strength = signals.get("relative_strength") if isinstance(signals.get("relative_strength"), dict) else {}
        warnings = self._strings(snapshot.get("warnings")) + self._strings(small.get("warnings"))
        reasons = self._strings(snapshot.get("reasons")) + self._strings(stock.get("reasons"))

        direction = self._normalize_direction(stock.get("direction") or snapshot.get("direction"))
        rvol = self._float(signals.get("relative_volume"))
        spread_pct = self._float(selected.get("spread_pct"))
        max_loss = self._float(selected.get("max_loss_dollars"))
        dte = self._float(selected.get("days_to_expiration"))
        stock_score = self._float(stock.get("score") or snapshot.get("score"))
        priority_score = self._float(small.get("priority_score"))
        friction_score = self._float(small.get("friction_adjusted_score") or friction.get("score"))
        vwap_state = "above" if signals.get("above_vwap") else "below" if signals.get("below_vwap") else "unknown"

        dimensions = {
            "setup_type": stock.get("setup_type") or snapshot.get("setup_type") or "unknown",
            "direction": direction or "unknown",
            "vwap_state": vwap_state,
            "relative_strength_label": relative_strength.get("label") or "unknown",
            "rvol_bucket": self._rvol_bucket(rvol),
            "stock_score_bucket": self._score_bucket(stock_score),
            "priority_bucket": self._score_bucket(priority_score),
            "friction_band": small.get("friction_band") or friction.get("band") or "unknown",
            "friction_score_bucket": self._score_bucket(friction_score),
            "dte_bucket": self._dte_bucket(dte),
            "spread_bucket": self._spread_bucket(spread_pct),
            "max_loss_bucket": self._max_loss_bucket(max_loss),
        }
        tags = self._tags(dimensions, warnings, reasons)
        setup_key = "|".join(f"{key}:{value}" for key, value in dimensions.items() if key not in {"priority_bucket", "stock_score_bucket"})
        return {
            "ticker": self._ticker(snapshot),
            "contract_symbol": selected.get("contract_symbol"),
            "setup_key": setup_key,
            "dimensions": dimensions,
            "tags": tags,
            "raw_values": {
                "stock_score": stock_score,
                "priority_score": priority_score,
                "friction_score": friction_score,
                "relative_volume": rvol,
                "spread_pct": spread_pct,
                "days_to_expiration": dte,
                "max_loss_dollars": max_loss,
            },
            "review_only": True,
            "can_place_order_from_this_mcp": False,
        }

    def compare_snapshot(self, snapshot: dict[str, Any], limit: int = 100) -> dict[str, Any]:
        fingerprint = self.build_fingerprint(snapshot)
        review_matches = self._similar_reviews(fingerprint, limit)
        lesson_matches = self._similar_lessons(fingerprint, limit)
        payload = {
            "status": "SETUP_MEMORY_READY",
            "fingerprint": fingerprint,
            "similar_review_summary": self._review_summary(review_matches),
            "similar_lesson_summary": self._lesson_summary(lesson_matches),
            "memory_signal": self._memory_signal(review_matches, lesson_matches),
            "similar_reviews": review_matches[:10],
            "similar_lessons": lesson_matches[:10],
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
            "notes": "Setup memory is advisory only. It does not approve trades or alter gates.",
        }
        return payload

    def _similar_reviews(self, fingerprint: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        matches = []
        for event in self.events.recent("candidate_options_review", limit):
            payload = event.get("payload") or {}
            candidate_fp = self.build_fingerprint(payload)
            score, reasons = self._similarity(fingerprint, candidate_fp)
            if score < 0.45:
                continue
            small = payload.get("small_account_review") or {}
            matches.append(
                {
                    "similarity": score,
                    "matched_on": reasons,
                    "timestamp": event.get("timestamp"),
                    "ticker": payload.get("ticker"),
                    "status": payload.get("status"),
                    "small_status": small.get("status"),
                    "priority_score": small.get("priority_score"),
                    "friction_score": small.get("friction_adjusted_score"),
                    "friction_band": small.get("friction_band"),
                    "warnings": payload.get("warnings") or small.get("warnings") or [],
                }
            )
        return sorted(matches, key=lambda item: item["similarity"], reverse=True)

    def _similar_lessons(self, fingerprint: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        matches = []
        for event in self.events.recent("learning_outcome_classification", limit):
            payload = event.get("payload") or {}
            lesson_fp = self._fingerprint_from_lesson(payload)
            score, reasons = self._similarity(fingerprint, lesson_fp)
            if score < 0.35:
                current_tags = set(fingerprint.get("tags") or [])
                lesson_tags = set(lesson_fp.get("tags") or [])
                if not (current_tags and current_tags.intersection(lesson_tags)):
                    continue
            outcome = payload.get("outcome_summary") or {}
            matches.append(
                {
                    "similarity": score,
                    "matched_on": reasons,
                    "timestamp": event.get("timestamp"),
                    "ticker": payload.get("ticker"),
                    "classification": payload.get("classification"),
                    "direction": payload.get("direction"),
                    "lesson_tags": payload.get("lesson_tags") or [],
                    "directional_return": outcome.get("directional_return"),
                    "reason": payload.get("reason"),
                }
            )
        return sorted(matches, key=lambda item: item["similarity"], reverse=True)

    def _fingerprint_from_lesson(self, lesson: dict[str, Any]) -> dict[str, Any]:
        summary = lesson.get("snapshot_summary") or {}
        signals = summary.get("signals") or {}
        tags = [str(tag) for tag in lesson.get("lesson_tags") or []]
        dimensions = {
            "setup_type": "unknown",
            "direction": self._normalize_direction(summary.get("direction")) or "unknown",
            "vwap_state": "above" if signals.get("above_vwap") else "below" if signals.get("below_vwap") else "unknown",
            "relative_strength_label": "unknown",
            "rvol_bucket": self._rvol_bucket(self._float(signals.get("relative_volume"))),
            "stock_score_bucket": self._score_bucket(self._float(summary.get("stock_score"))),
            "priority_bucket": self._score_bucket(self._float(summary.get("priority_score"))),
            "friction_band": "unknown",
            "friction_score_bucket": "unknown",
            "dte_bucket": "unknown",
            "spread_bucket": "wide" if "wide_spread" in tags else "unknown",
            "max_loss_bucket": "high" if "max_loss" in tags else "unknown",
        }
        return {"dimensions": dimensions, "tags": tags}

    def _similarity(self, current: dict[str, Any], other: dict[str, Any]) -> tuple[float, list[str]]:
        current_dims = current.get("dimensions") or {}
        other_dims = other.get("dimensions") or {}
        weights = {
            "setup_type": 0.8,
            "direction": 1.2,
            "vwap_state": 1.0,
            "relative_strength_label": 0.8,
            "rvol_bucket": 0.8,
            "friction_band": 1.0,
            "dte_bucket": 0.8,
            "spread_bucket": 0.8,
            "max_loss_bucket": 0.8,
        }
        earned = 0.0
        possible = 0.0
        reasons = []
        for key, weight in weights.items():
            a = current_dims.get(key)
            b = other_dims.get(key)
            if not a or not b or a == "unknown" or b == "unknown":
                continue
            possible += weight
            if a == b:
                earned += weight
                reasons.append(f"{key}:{a}")
        current_tags = set(current.get("tags") or [])
        other_tags = set(other.get("tags") or [])
        tag_union = current_tags.union(other_tags)
        if tag_union:
            tag_overlap = current_tags.intersection(other_tags)
            possible += 1.0
            earned += len(tag_overlap) / len(tag_union)
            if tag_overlap:
                reasons.extend(f"tag:{tag}" for tag in sorted(tag_overlap))
        return (round(earned / possible, 4) if possible else 0.0, reasons)

    def _review_summary(self, matches: list[dict[str, Any]]) -> dict[str, Any]:
        statuses = Counter(str(item.get("status")) for item in matches)
        small_statuses = Counter(str(item.get("small_status")) for item in matches)
        friction_scores = [self._float(item.get("friction_score")) for item in matches]
        friction_scores = [score for score in friction_scores if score is not None]
        return {
            "sample_size": len(matches),
            "status_counts": dict(statuses),
            "small_status_counts": dict(small_statuses),
            "average_friction_score": round(mean(friction_scores), 2) if friction_scores else None,
        }

    def _lesson_summary(self, matches: list[dict[str, Any]]) -> dict[str, Any]:
        classifications = Counter(str(item.get("classification")) for item in matches)
        returns = [self._float(item.get("directional_return")) for item in matches]
        returns = [value for value in returns if value is not None]
        tags: Counter[str] = Counter()
        for item in matches:
            tags.update(str(tag) for tag in item.get("lesson_tags") or [])
        return {
            "sample_size": len(matches),
            "classification_counts": dict(classifications),
            "top_lesson_tags": dict(tags.most_common(8)),
            "average_directional_return": round(mean(returns), 5) if returns else None,
        }

    def _memory_signal(self, reviews: list[dict[str, Any]], lessons: list[dict[str, Any]]) -> str:
        if not reviews and not lessons:
            return "NO_MEMORY_YET"
        classifications = Counter(str(item.get("classification")) for item in lessons)
        if classifications["FALSE_POSITIVE"] + classifications["GOOD_BLOCK"] >= 2:
            return "SIMILAR_RISK_SEEN_BEFORE"
        if classifications["GOOD_SIGNAL"] + classifications["MISSED_MOVE"] + classifications["BAD_CONTRACT_OR_TOO_STRICT"] >= 2:
            return "SIMILAR_EDGE_SEEN_BEFORE"
        if reviews:
            return "SIMILAR_REVIEW_HISTORY_FOUND"
        return "MIXED_OR_THIN_MEMORY"

    def _tags(self, dimensions: dict[str, Any], warnings: list[str], reasons: list[str]) -> list[str]:
        joined = " ".join(warnings + reasons).lower()
        tags = set()
        if dimensions["rvol_bucket"] in {"low", "unknown"}:
            tags.add(f"rvol_{dimensions['rvol_bucket']}")
        if dimensions["friction_band"] in {"HIGH_FRICTION", "BLOCKED_BY_FRICTION"}:
            tags.add(dimensions["friction_band"].lower())
        if dimensions["spread_bucket"] in {"wide", "very_wide"}:
            tags.add("wide_spread")
        if dimensions["dte_bucket"] in {"0dte", "1dte"}:
            tags.add(dimensions["dte_bucket"])
        if dimensions["max_loss_bucket"] in {"elevated", "high"}:
            tags.add("max_loss")
        if "vwap" in joined and "conflict" in joined:
            tags.add("vwap_conflict")
        if "no acceptable small-account contract" in joined:
            tags.add("no_small_account_contract")
        if "friction" in joined:
            tags.add("friction_warning")
        return sorted(tags)

    def _ticker(self, snapshot: dict[str, Any]) -> str:
        stock = snapshot.get("stock_setup") if isinstance(snapshot.get("stock_setup"), dict) else {}
        return str(snapshot.get("ticker") or stock.get("ticker") or "UNKNOWN").upper()

    def _rvol_bucket(self, value: float | None) -> str:
        if value is None:
            return "unknown"
        if value < 0.8:
            return "low"
        if value < 1.15:
            return "soft"
        if value < 2.0:
            return "confirmed"
        return "strong"

    def _score_bucket(self, value: float | None) -> str:
        if value is None:
            return "unknown"
        if value >= 85:
            return "excellent"
        if value >= 70:
            return "good"
        if value >= 55:
            return "marginal"
        return "weak"

    def _dte_bucket(self, value: float | None) -> str:
        if value is None:
            return "unknown"
        if value <= 0:
            return "0dte"
        if value == 1:
            return "1dte"
        if value <= 3:
            return "2_3dte"
        if value <= 7:
            return "4_7dte"
        return "8plus_dte"

    def _spread_bucket(self, value: float | None) -> str:
        if value is None:
            return "unknown"
        if value <= 0.05:
            return "tight"
        if value <= 0.08:
            return "ok"
        if value <= 0.15:
            return "wide"
        return "very_wide"

    def _max_loss_bucket(self, value: float | None) -> str:
        if value is None:
            return "unknown"
        if value <= 25:
            return "tiny"
        if value <= 50:
            return "small"
        if value <= 75:
            return "elevated"
        return "high"

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
