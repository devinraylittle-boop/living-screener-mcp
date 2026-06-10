from __future__ import annotations

import unittest
from datetime import UTC, datetime

from app.mcp_server import _log_manual_broker_action
from tests.helpers import TempContainer


class ManualBrokerActionTests(unittest.TestCase):
    def test_pending_buy_action_creates_recheck_card_without_mcp_broker_action(self) -> None:
        with TempContainer() as container:
            result = _log_manual_broker_action(
                container,
                {
                    "ticker": "SOFI",
                    "contract_symbol": "SOFI260612P00015000",
                    "action_type": "pending_buy",
                    "order_status": "queued",
                    "side": "buy",
                    "direction": "put",
                    "limit_price": 0.08,
                    "quantity": 1,
                    "submitted_at": "2026-06-10T14:30:00+00:00",
                    "is_options_order": True,
                },
            )

        self.assertEqual(result["event_type"], "manual_broker_action")
        self.assertEqual(result["status"], "MANUAL_ACTION_PENDING_RECHECK_REQUIRED")
        self.assertTrue(result["pending_buy"])
        self.assertEqual(result["recheck_request"]["tool"], "review_pending_buy_order")
        self.assertEqual(result["recheck_request"]["endpoint"], "/trade/pending-recheck")
        self.assertEqual(result["recheck_request"]["payload"]["direction"], "put")
        self.assertFalse(result["mcp_broker_action"])
        self.assertFalse(result["order_placed_by_mcp"])
        self.assertFalse(result["order_submitted_by_mcp"])
        self.assertFalse(result["order_canceled_by_mcp"])
        self.assertFalse(result["can_place_order_from_this_mcp"])

    def test_non_pending_manual_note_logs_without_recheck(self) -> None:
        with TempContainer() as container:
            result = _log_manual_broker_action(
                container,
                {
                    "ticker": "SOFI",
                    "action_type": "pass",
                    "order_status": "not_placed",
                    "side": "none",
                    "submitted_at": datetime(2026, 6, 10, 14, 30, tzinfo=UTC),
                },
            )

        self.assertEqual(result["status"], "MANUAL_ACTION_LOGGED")
        self.assertFalse(result["pending_buy"])
        self.assertIsNone(result["recheck_request"])
        self.assertTrue(result["broker_action_was_user_reported"])
        self.assertFalse(result["mcp_broker_action"])


if __name__ == "__main__":
    unittest.main()
