from __future__ import annotations

import unittest

from app.services.learning_service import LearningService
from tests.helpers import TempContainer


class LearningServiceTests(unittest.TestCase):
    def test_passed_review_that_loses_is_false_positive(self) -> None:
        with TempContainer() as container:
            service = LearningService(container.events)
            result = service.classify_review_outcome(
                {
                    "ticker": "SOFI",
                    "status": "REVIEW_ONLY_OPTIONS_READY",
                    "stock_setup": {
                        "ticker": "SOFI",
                        "status": "CANDIDATE",
                        "score": 94,
                        "direction": "short",
                        "key_signals": {"relative_volume": 0.7},
                    },
                    "small_account_review": {
                        "status": "SMALL_ACCOUNT_SCALP_ACCEPTABLE",
                        "priority_score": 95,
                        "warnings": ["Selected contract spread is wider than preferred."],
                    },
                },
                {
                    "current_return_pct": -0.006,
                    "max_favorable_excursion": 0.001,
                    "max_adverse_excursion": -0.01,
                    "verdict": "HURT",
                },
            )

        self.assertEqual(result["classification"], "FALSE_POSITIVE")
        self.assertIn("low_relative_volume", result["lesson_tags"])
        self.assertIn("wide_spread", result["lesson_tags"])
        self.assertFalse(result["can_place_order_from_this_mcp"])

    def test_pass_item_that_moves_is_missed_move(self) -> None:
        with TempContainer() as container:
            service = LearningService(container.events)
            result = service.classify_review_outcome(
                {
                    "ticker": "SMCI",
                    "status": "PASS",
                    "score": 60,
                    "direction": "short",
                    "key_signals": {"relative_volume": 0.9},
                    "reasons": ["Score below scalp_review threshold."],
                },
                {
                    "current_return_pct": 0.004,
                    "max_favorable_excursion": 0.012,
                    "max_adverse_excursion": -0.002,
                    "verdict": "HELPED",
                },
            )

        self.assertEqual(result["classification"], "MISSED_MOVE")
        self.assertIn("low_relative_volume", result["lesson_tags"])

    def test_rule_proposals_require_samples_and_do_not_auto_apply(self) -> None:
        with TempContainer() as container:
            service = LearningService(container.events)
            samples = [
                {
                    "classification": "FALSE_POSITIVE",
                    "lesson_tags": ["wide_spread"],
                    "outcome_summary": {"directional_return": -0.005},
                },
                {
                    "classification": "FALSE_POSITIVE",
                    "lesson_tags": ["wide_spread"],
                    "outcome_summary": {"directional_return": -0.004},
                },
                {
                    "classification": "GOOD_SIGNAL",
                    "lesson_tags": ["wide_spread"],
                    "outcome_summary": {"directional_return": 0.002},
                },
            ]

            result = service.generate_rule_proposals(samples, min_samples=3)

        self.assertEqual(result["status"], "RULE_PROPOSALS_READY")
        self.assertTrue(result["do_not_auto_apply"])
        self.assertEqual(result["proposals"][0]["action"], "tighten_spread_penalty")


if __name__ == "__main__":
    unittest.main()
