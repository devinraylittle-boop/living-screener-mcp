from __future__ import annotations

import unittest

from tools.stage3_readiness_report import build_report


class Stage3ReadinessReportTests(unittest.TestCase):
    def test_stage3_report_marks_code_ready_without_runtime_auth(self) -> None:
        report = build_report()

        self.assertEqual(report["status"], "STAGE3_CODE_READY")
        self.assertEqual(report["runtime_status"], "CODE_READY_OPERATOR_AUTH_REQUIRED")
        self.assertFalse(report["can_place_order_from_this_report"])
        self.assertEqual(report["stage3_limits"]["max_order_notional_usd"], 10.0)
        self.assertEqual(report["stage3_limits"]["max_daily_loss_usd"], 5.0)
        self.assertTrue(report["checks"]["stage3_parser_refuses_cap_violation"])
        self.assertTrue(report["checks"]["stage4_requires_all_gates"])


if __name__ == "__main__":
    unittest.main()

