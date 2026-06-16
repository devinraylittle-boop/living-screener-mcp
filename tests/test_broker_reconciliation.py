from __future__ import annotations

import unittest

from tools.broker_reconciliation import build_reconciliation_report


class BrokerReconciliationTests(unittest.TestCase):
    def test_report_is_read_only_and_ready_for_clean_snapshot(self) -> None:
        report = build_reconciliation_report(
            snapshot={
                "broker": "alpaca",
                "scope": "paper",
                "positions": [{"symbol": "RBLX", "qty": "1"}],
                "open_orders": [{"symbol": "SOFI", "status": "new"}],
            }
        )

        self.assertEqual(report["status"], "BROKER_RECONCILIATION_READY")
        self.assertFalse(report["can_place_order_from_this_report"])
        self.assertTrue(report["review_only"])
        self.assertEqual(report["symbols_with_positions"], ["RBLX"])
        self.assertEqual(report["symbols_with_open_orders"], ["SOFI"])

    def test_duplicate_open_order_symbols_block_reconciliation(self) -> None:
        report = build_reconciliation_report(
            snapshot={
                "positions": [],
                "open_orders": [
                    {"symbol": "RBLX", "status": "new"},
                    {"symbol": "RBLX", "status": "queued"},
                ],
            }
        )

        self.assertEqual(report["status"], "BROKER_RECONCILIATION_BLOCKED")
        self.assertIn("RBLX", report["duplicate_open_order_symbols"])
        self.assertIn("no_duplicate_open_orders", report["blockers"])

    def test_missing_snapshot_blocks_stage_four_runtime_reconciliation(self) -> None:
        report = build_reconciliation_report()

        self.assertEqual(report["status"], "BROKER_RECONCILIATION_BLOCKED")
        self.assertIn("broker_snapshot_supplied", report["blockers"])


if __name__ == "__main__":
    unittest.main()
