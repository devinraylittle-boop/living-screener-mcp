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
        self.assertIn("session_risk", result["action_links"])
        self.assertIn("market_open_observer", result["action_links"])
        self.assertIn("No market orders.", result["absolute_no_trade_rules"])
        self.assertEqual(result["latest"]["session_risk_guard"]["status"], "SESSION_RISK_CLEAR")
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

    def test_launch_blocks_new_ideas_after_real_cash_loss_lockout(self) -> None:
        with TempContainer() as container:
            for index in range(3):
                container.events.log(
                    "manual_broker_action",
                    {
                        "status": "MANUAL_ACTION_LOGGED",
                        "ticker": "SOFI",
                        "contract_symbol": f"SOFI260612P0001500{index}",
                        "action_type": "sell_to_close",
                        "order_status": "filled",
                        "side": "sell",
                        "is_real_cash": True,
                        "is_closing_action": True,
                        "pnl_dollars": -1.0,
                    },
                )
            result = _get_trading_day_launch_checklist(container, ["SOFI"], account_value=50, max_candidates=25)

        self.assertEqual(result["status"], "LAUNCH_SESSION_RISK_BLOCKED")
        self.assertEqual(result["latest"]["session_risk_guard"]["status"], "SESSION_RISK_BLOCKED")
        self.assertIn("No new manual idea while session risk is SESSION_RISK_BLOCKED.", result["absolute_no_trade_rules"])


if __name__ == "__main__":
    unittest.main()
