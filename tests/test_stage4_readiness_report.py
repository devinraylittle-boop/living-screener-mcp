from __future__ import annotations

import unittest

from tools.stage4_readiness_report import build_report


class Stage4ReadinessReportTests(unittest.TestCase):
    def test_stage4_report_is_code_ready_but_runtime_blocked(self) -> None:
        report = build_report()

        self.assertEqual(report["status"], "STAGE4_CODE_READY_RUNTIME_BLOCKED")
        self.assertEqual(report["runtime_status"], "BLOCKED_UNTIL_READINESS_GATES_PASS")
        self.assertFalse(report["can_place_order_from_this_report"])
        self.assertTrue(report["code_checks"]["stage4_live_startup_refused_until_gates_pass"])
        self.assertFalse(report["runtime_checks"]["paper_promotion_ready"])
        self.assertFalse(report["runtime_checks"]["broker_reconciliation_ready"])
        self.assertIn("external_alerting_ready", report["runtime_blockers"])
        self.assertIn("secrets_rotation_confirmed", report["runtime_blockers"])


if __name__ == "__main__":
    unittest.main()
