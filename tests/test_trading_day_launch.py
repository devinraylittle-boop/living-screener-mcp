from __future__ import annotations

import unittest

from app.mcp_server import _get_trading_day_launch_checklist
from tests.helpers import TempContainer


class TradingDayLaunchTests(unittest.TestCase):
    def test_launch_starts_with_health_and_observer_when_no_state_exists(self) -> None:
        with TempContainer() as container:
            result = _get_trading_day_launch_checklist(container, ["SOFI", "SMCI"], account_value=50, max_candidates=25)

        self.assertEqual(result["event_type"], "trading_day_launch_checklist")
        self.assertEqual(result["status"], "LAUNCH_START_HERE")
        self.assertIn("health_full", result["action_links"])
        self.assertIn("market_open_observer", result["action_links"])
        self.assertIn("No market orders.", result["absolute_no_trade_rules"])
        self.assertFalse(result["can_place_order_from_this_mcp"])
        self.assertFalse(result["broker_action"])

    def test_launch_prioritizes_pending_buy_recheck(self) -> None:
        with TempContainer() as container:
            container.events.log(
                "manual_broker_action",
                {
                    "status": "MANUAL_ACTION_PENDING_RECHECK_REQUIRED",
                    "pending_buy": True,
                    "ticker": "SOFI",
                    "review_only": True,
                    "can_place_order_from_this_mcp": False,
                },
            )
            result = _get_trading_day_launch_checklist(container, ["SOFI"], account_value=50, max_candidates=25)

        self.assertEqual(result["status"], "LAUNCH_PENDING_RECHECK_REQUIRED")
        self.assertIn("pending-buy recheck", result["next_action"].lower())
        self.assertEqual(result["latest"]["manual_broker_action"]["status"], "MANUAL_ACTION_PENDING_RECHECK_REQUIRED")


if __name__ == "__main__":
    unittest.main()
