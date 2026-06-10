from __future__ import annotations

import unittest

from app.mcp_server import _summarize_trading_day_alerts
from tests.helpers import TempContainer


class TradingDayAlertsTests(unittest.TestCase):
    def test_pending_buy_recheck_is_urgent_top_alert(self) -> None:
        with TempContainer() as container:
            container.events.log(
                "trading_day_heartbeat",
                {
                    "status": "HEARTBEAT_MANUAL_REVIEW_READY",
                    "next_action": "Inspect manually.",
                    "action_links": {"manual_trade_desk": "/trade/manual-desk"},
                    "review_only": True,
                    "can_place_order_from_this_mcp": False,
                },
            )
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
            result = _summarize_trading_day_alerts(container, 50)

        self.assertEqual(result["status"], "ALERTS_REQUIRE_ACTION")
        self.assertEqual(result["top_level"], "URGENT")
        self.assertEqual(result["alerts"][0]["type"], "PENDING_BUY_RECHECK")
        self.assertFalse(result["can_place_order_from_this_mcp"])
        self.assertFalse(result["broker_action"])

    def test_quiet_alerts_still_remind_checkpoint(self) -> None:
        with TempContainer() as container:
            result = _summarize_trading_day_alerts(container, 50)

        self.assertEqual(result["status"], "ALERTS_INFORMATIONAL")
        self.assertEqual(result["alerts"][0]["type"], "CHECKPOINT_NOT_EXPORTED")
        self.assertEqual(result["action_links"]["journal_checkpoint"], "/journal/checkpoint?limit=500&format=json")


if __name__ == "__main__":
    unittest.main()
