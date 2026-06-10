from __future__ import annotations

import copy
import unittest

from app.mcp_server import _export_journal_checkpoint, _restore_journal_checkpoint
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

    def test_checkpoint_restore_rehydrates_events_and_dedupes_repeats(self) -> None:
        with TempContainer() as source:
            source.events.log("live_review_cycle", {"status": "NO_TRADE_PLAN", "ticker": "SOFI"})
            source.events.log("manual_option_paper_close", {"status": "PAPER_OPTION_CLOSED", "pnl_dollars": 2.0})
            checkpoint = _export_journal_checkpoint(source, limit=10, event_types=None)

        with TempContainer() as target:
            first = _restore_journal_checkpoint(target, copy.deepcopy(checkpoint), "unit_test_restore", 10)
            second = _restore_journal_checkpoint(target, copy.deepcopy(checkpoint), "unit_test_restore", 10)
            restored_cycles = target.events.recent("live_review_cycle", 10)

        self.assertEqual(first["status"], "CHECKPOINT_RESTORE_READY")
        self.assertEqual(first["restored_count"], checkpoint["event_count"])
        self.assertEqual(first["skipped_duplicate_count"], 0)
        self.assertEqual(second["status"], "CHECKPOINT_RESTORE_NO_NEW_EVENTS")
        self.assertEqual(second["restored_count"], 0)
        self.assertEqual(second["skipped_duplicate_count"], checkpoint["event_count"])
        self.assertEqual(restored_cycles[0]["payload"]["status"], "NO_TRADE_PLAN")
        self.assertIn("_restored_from_checkpoint", restored_cycles[0]["payload"])
        self.assertFalse(first["can_place_order_from_this_mcp"])

    def test_checkpoint_restore_rejects_bad_payload(self) -> None:
        with TempContainer() as container:
            result = _restore_journal_checkpoint(container, {"events": "bad"}, "unit_test_restore", 10)

        self.assertEqual(result["status"], "CHECKPOINT_RESTORE_REJECTED")
        self.assertEqual(result["restored_count"], 0)
        self.assertFalse(result["can_cancel_order_from_this_mcp"])


if __name__ == "__main__":
    unittest.main()
