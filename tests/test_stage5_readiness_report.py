from __future__ import annotations

import unittest

from tools.stage5_readiness_report import build_report


class Stage5ReadinessReportTests(unittest.TestCase):
    def test_stage5_report_refuses_live_autonomy(self) -> None:
        report = build_report()

        self.assertEqual(report["final_decision"], "NO_GO_LIVE_AUTONOMY")
        self.assertEqual(report["enabled_mode"], "STAGE_2_ALPACA_PAPER_ONLY")
        self.assertFalse(report["can_place_order_from_this_report"])
        self.assertTrue(report["critical_checks"]["stage5_startup_refused_until_all_gates_pass"])
        self.assertTrue(report["critical_checks"]["app_layer_fail_closed"])
        self.assertEqual(report["risk_limits_chosen"]["live_max_daily_loss_usd"], 0.0)
        self.assertEqual(report["risk_limits_chosen"]["live_max_open_positions"], 0)
        self.assertFalse(report["critical_checks"]["execution_order_validated"])
        self.assertIn("stage5_90_day_clean_record_not_available", report["runtime_blockers"])
        self.assertIn("execution_order_has_unresolved_authority_or_risk_fields", report["runtime_blockers"])


if __name__ == "__main__":
    unittest.main()
