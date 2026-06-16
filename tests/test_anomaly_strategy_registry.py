from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "anomaly_strategy_registry.json"


class AnomalyStrategyRegistryTests(unittest.TestCase):
    def test_registry_is_parseable_and_live_safe_by_default(self) -> None:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

        self.assertFalse(registry["default_policy"]["cash_live_enabled"])
        self.assertTrue(registry["default_policy"]["paper_enabled"])
        self.assertTrue(registry["default_policy"]["requires_manual_promotion"])
        self.assertGreaterEqual(registry["promotion_gate"]["min_closed_paper_trades"], 50)
        self.assertGreaterEqual(registry["promotion_gate"]["min_distinct_market_days"], 15)

    def test_each_strategy_has_required_research_contract(self) -> None:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        strategies = registry["strategies"]

        self.assertGreaterEqual(len(strategies), 5)
        self.assertEqual([row["priority"] for row in strategies], sorted(row["priority"] for row in strategies))
        for strategy in strategies:
            with self.subTest(strategy=strategy["id"]):
                self.assertFalse(strategy["cash_live_enabled"])
                self.assertIn(strategy["default_lane"], {"paper", "shadow"})
                self.assertTrue(strategy["hypothesis"])
                self.assertTrue(strategy["required_data"])
                self.assertTrue(strategy["features"])
                self.assertTrue(strategy["entry_rule"])
                self.assertTrue(strategy["exit_rule"])
                self.assertTrue(strategy["risk_notes"])


if __name__ == "__main__":
    unittest.main()
