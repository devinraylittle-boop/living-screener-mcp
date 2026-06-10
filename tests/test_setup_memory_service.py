from __future__ import annotations

import unittest

from app.services.setup_memory_service import SetupMemoryService
from tests.helpers import TempContainer


def snapshot(ticker: str = "SMCI") -> dict:
    return {
        "ticker": ticker,
        "status": "REVIEW_ONLY_OPTIONS_READY",
        "stock_setup": {
            "ticker": ticker,
            "status": "CANDIDATE",
            "score": 76,
            "direction": "short",
            "setup_type": "scalp_review",
            "key_signals": {
                "relative_volume": 0.95,
                "above_vwap": False,
                "below_vwap": True,
                "relative_strength": {"label": "mixed_vs_spy"},
            },
        },
        "small_account_review": {
            "status": "SMALL_ACCOUNT_SCALP_ACCEPTABLE",
            "priority_score": 66,
            "friction_adjusted_score": 80,
            "friction_band": "MANAGEABLE_FRICTION",
            "selected_contract": {
                "contract_symbol": f"{ticker}TEST",
                "days_to_expiration": 2,
                "spread_pct": 0.11,
                "max_loss_dollars": 29,
            },
            "warnings": ["Selected contract spread is wider than preferred for a scalp."],
        },
        "warnings": ["Scalp relative volume 0.95 is below the preferred floor 1.15."],
    }


class SetupMemoryServiceTests(unittest.TestCase):
    def test_fingerprint_captures_review_shape(self) -> None:
        with TempContainer() as container:
            service = SetupMemoryService(container.events)
            result = service.build_fingerprint(snapshot())

        self.assertEqual(result["dimensions"]["direction"], "short")
        self.assertEqual(result["dimensions"]["vwap_state"], "below")
        self.assertEqual(result["dimensions"]["friction_band"], "MANAGEABLE_FRICTION")
        self.assertIn("wide_spread", result["tags"])

    def test_compare_snapshot_finds_similar_review_and_lesson(self) -> None:
        with TempContainer() as container:
            service = SetupMemoryService(container.events)
            prior = snapshot("TSLA")
            container.events.log("candidate_options_review", prior)
            container.events.log(
                "learning_outcome_classification",
                {
                    "ticker": "TSLA",
                    "classification": "FALSE_POSITIVE",
                    "direction": "short",
                    "lesson_tags": ["wide_spread", "low_relative_volume"],
                    "snapshot_summary": {
                        "direction": "short",
                        "stock_score": 76,
                        "priority_score": 66,
                        "signals": {"relative_volume": 0.95, "above_vwap": False, "below_vwap": True},
                    },
                    "outcome_summary": {"directional_return": -0.004},
                },
            )
            result = service.compare_snapshot(snapshot("SMCI"))

        self.assertEqual(result["status"], "SETUP_MEMORY_READY")
        self.assertGreaterEqual(result["similar_review_summary"]["sample_size"], 1)
        self.assertGreaterEqual(result["similar_lesson_summary"]["sample_size"], 1)
        self.assertIn(result["memory_signal"], {"SIMILAR_REVIEW_HISTORY_FOUND", "MIXED_OR_THIN_MEMORY"})
        self.assertFalse(result["can_place_order_from_this_mcp"])


if __name__ == "__main__":
    unittest.main()
