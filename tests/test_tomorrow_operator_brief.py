from __future__ import annotations

import unittest

from app.mcp_server import _get_tomorrow_operator_brief
from tests.helpers import TempContainer


class TomorrowOperatorBriefTests(unittest.TestCase):
    def test_operator_brief_is_review_only_and_actionable(self) -> None:
        with TempContainer() as container:
            result = _get_tomorrow_operator_brief(container, ["SOFI", "SMCI"], 50, 25)

        self.assertEqual(result["event_type"], "tomorrow_operator_brief")
        self.assertEqual(result["status"], "OPERATOR_READY_TO_START")
        self.assertIn("morning_sequence", result)
        self.assertIn("chatgpt_connector_fallback", result)
        self.assertIn("session_risk_guard", result)
        self.assertIn("day_monitor", result["action_links"])
        self.assertFalse(result["can_place_order_from_this_mcp"])
        self.assertFalse(result["can_cancel_order_from_this_mcp"])

    def test_operator_brief_uses_configured_universe_when_tickers_omitted(self) -> None:
        with TempContainer() as container:
            result = _get_tomorrow_operator_brief(container, None, 50, 25)

        self.assertEqual(result["status"], "OPERATOR_READY_TO_START")
        self.assertIn("SPY", result["universe"])
        self.assertTrue(result["action_links"]["day_monitor"].startswith("/ops/day-monitor?tickers="))

    def test_operator_brief_prioritizes_pending_recheck(self) -> None:
        with TempContainer() as container:
            container.events.log(
                "manual_broker_action",
                {"status": "MANUAL_ACTION_PENDING_RECHECK_REQUIRED", "pending_buy": True},
            )
            result = _get_tomorrow_operator_brief(container, ["SOFI"], 50, 25)

        self.assertEqual(result["status"], "OPERATOR_PENDING_RECHECK_REQUIRED")
        self.assertIn("pending-buy", result["next_action"].lower())

    def test_operator_brief_blocks_when_session_risk_is_full(self) -> None:
        with TempContainer() as container:
            for index in range(2):
                container.events.log(
                    "manual_option_paper_entry",
                    {
                        "status": "PAPER_OPTION_ENTRY_OPEN",
                        "ticker": "SOFI",
                        "contract_symbol": f"SOFI260612P0001500{index}",
                        "entry_debit_dollars": 8.0,
                    },
                )
            result = _get_tomorrow_operator_brief(container, ["SOFI"], 50, 25)

        self.assertEqual(result["status"], "OPERATOR_SESSION_RISK_BLOCKED")
        self.assertEqual(result["session_risk_guard"]["status"], "SESSION_RISK_BLOCKED")


if __name__ == "__main__":
    unittest.main()
