from __future__ import annotations

import unittest
from pathlib import Path

from app.mcp_server import get_safety_config
from app.models.enums import Direction, OrderType
from app.models.schemas import TradePlan
from tests.helpers import TempContainer


class SafetyTests(unittest.TestCase):
    def test_safety_config_blocks_execution(self) -> None:
        result = get_safety_config()
        self.assertTrue(result["review_only"])
        self.assertFalse(result["place_orders"])
        self.assertFalse(result["market_orders_allowed"])
        self.assertFalse(result["can_place_order_from_this_mcp"])
        self.assertFalse(result["can_cancel_order_from_this_mcp"])
        self.assertEqual(result["pending_buy_recheck_seconds"], 60)

    def test_execution_request_is_blocked(self) -> None:
        with TempContainer() as container:
            result = container.risk.check(TradePlan("KO", Direction.LONG, "day_trade", 50, 5, requested_execution=True))
        self.assertEqual(result["status"], "BLOCK")

    def test_market_order_is_blocked(self) -> None:
        with TempContainer() as container:
            result = container.risk.check(TradePlan("KO", Direction.LONG, "day_trade", 50, 5, order_type=OrderType.MARKET))
        self.assertEqual(result["status"], "BLOCK")

    def test_no_robinhood_api_imports(self) -> None:
        matches = []
        for path in (Path(__file__).resolve().parents[1] / "app").rglob("*.py"):
            lowered = path.read_text(encoding="utf-8").lower()
            if any(pattern in lowered for pattern in ["import robinhood", "from robinhood", "robin_stocks", "api.robinhood"]):
                matches.append(path.name)
        self.assertEqual(matches, [])
