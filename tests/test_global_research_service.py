from __future__ import annotations

import unittest

from app.services.global_research_service import GlobalResearchService
from tests.helpers import TempContainer


class GlobalResearchServiceTests(unittest.TestCase):
    def test_offhours_plan_is_research_only(self) -> None:
        with TempContainer() as container:
            service = GlobalResearchService(container.events)
            result = service.offhours_plan()

        self.assertEqual(result["status"], "OFFHOURS_RESEARCH_READY")
        self.assertFalse(result["can_place_order_from_this_mcp"])
        self.assertIn("crypto", result["universes"])

    def test_evaluate_symbol_scores_expansion_candidate(self) -> None:
        with TempContainer() as container:
            service = GlobalResearchService(container.events)

        candles = []
        price = 100.0
        for index in range(40):
            if index < 32:
                high = price + 0.08
                low = price - 0.08
                close = price + (0.01 if index % 2 else -0.01)
            elif index < 39:
                high = price + 0.03
                low = price - 0.03
                close = price
            else:
                close = price + 1.2
                high = close + 0.25
                low = price - 0.02
            candles.append({"timestamp": f"t{index}", "open": price, "high": high, "low": low, "close": close, "volume": 1000 if index < 39 else 2500})
            price = close

        result = service._evaluate_symbol("ETH-USD", candles, "5m")

        self.assertEqual(result["status"], "STUDY_CANDIDATE")
        self.assertGreaterEqual(result["score"], 65)
        self.assertIn("compression_break", result["lesson_tags"])
        self.assertFalse(result["can_place_order_from_this_mcp"])

    def test_empty_symbol_fails_closed(self) -> None:
        with TempContainer() as container:
            service = GlobalResearchService(container.events)

        result = service._evaluate_symbol("EWJ", [], "5m")

        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["order_allowed"])

    def test_zero_volume_and_flat_ranges_use_price_move_fallbacks(self) -> None:
        with TempContainer() as container:
            service = GlobalResearchService(container.events)

        candles = []
        price = 100.0
        for index in range(35):
            if index == 34:
                price += 1.0
            else:
                price += 0.02
            candles.append({"timestamp": f"t{index}", "open": price, "high": price, "low": price, "close": price, "volume": 0})

        result = service._evaluate_symbol("BTC-USD", candles, "5m")

        features = result["feature_summary"]
        self.assertIsNone(features["relative_volume"])
        self.assertEqual(features["relative_volume_status"], "unavailable_or_zero_volume")
        self.assertEqual(features["range_expansion_source"], "close_to_close_proxy")
        self.assertIn("rvol_unavailable", result["lesson_tags"])
        self.assertNotIn("low_rvol", result["lesson_tags"])


if __name__ == "__main__":
    unittest.main()
