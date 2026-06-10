from __future__ import annotations

import unittest

from app.mcp_server import _export_journal_checkpoint
from tests.helpers import TempContainer


class JournalCheckpointTests(unittest.TestCase):
    def test_checkpoint_exports_recent_events_without_execution_power(self) -> None:
        with TempContainer() as container:
            container.events.log("live_review_cycle", {"status": "NO_TRADE_PLAN", "ticker": "SOFI"})
            container.events.log("manual_option_paper_close", {"status": "PAPER_OPTION_CLOSED", "pnl_dollars": 3.0})
            result = _export_journal_checkpoint(container, limit=10, event_types=None)

        self.assertEqual(result["status"], "JOURNAL_CHECKPOINT_READY")
        self.assertGreaterEqual(result["event_count"], 2)
        self.assertIn("live_review_cycle", result["event_type_counts"])
        self.assertIn("manual_option_paper_close", result["event_type_counts"])
        self.assertGreater(result["checkpoint_event_id"], 0)
        self.assertFalse(result["can_place_order_from_this_mcp"])
        self.assertFalse(result["can_cancel_order_from_this_mcp"])

    def test_checkpoint_can_filter_event_types(self) -> None:
        with TempContainer() as container:
            container.events.log("live_review_cycle", {"status": "NO_TRADE_PLAN"})
            container.events.log("manual_option_paper_close", {"status": "PAPER_OPTION_CLOSED"})
            result = _export_journal_checkpoint(container, limit=10, event_types=["manual_option_paper_close"])

        self.assertEqual(result["event_count"], 1)
        self.assertEqual(result["event_type_counts"], {"manual_option_paper_close": 1})
        self.assertEqual(result["events"][0]["event_type"], "manual_option_paper_close")


if __name__ == "__main__":
    unittest.main()
