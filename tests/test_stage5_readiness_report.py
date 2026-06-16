from __future__ import annotations

import unittest

from tools.stage5_readiness_report import build_report


class Stage5ReadinessReportTests(unittest.TestCase):
    def test_stage5_report_refuses_live_autonomy(self) -> None:
        report = build_report()

        self.assertEqual(
            report["final_decision"],
            "ALPACA_LIVE_CASH_AUTHORIZED_ROUTE_ADDED_NO_AUTONOMOUS_ORDERS_UNTIL_ACCOUNT_AND_STAGE_GATES_PASS",
        )
        self.assertEqual(report["status"], "STAGE5_ALPACA_LIVE_CASH_AUTHORIZED_RUNTIME_GATED")
        self.assertEqual(report["enabled_mode"], "STAGE_5_CASH_AUTONOMY_AUTHORIZED_ROUTES_RUNTIME_GATED")
        self.assertFalse(report["can_place_order_from_this_report"])
        self.assertTrue(report["critical_checks"]["stage5_startup_refused_until_all_gates_pass"])
        self.assertTrue(report["critical_checks"]["app_layer_fail_closed"])
        self.assertTrue(report["critical_checks"]["live_cash_authority_validated"])
        self.assertTrue(report["critical_checks"]["alpaca_live_cash_route_wired"])
        self.assertTrue(report["critical_checks"]["alpaca_live_endpoint_configurable"])
        self.assertEqual(report["risk_limits_chosen"]["live_max_daily_loss_usd"], 0.0)
        self.assertEqual(report["risk_limits_chosen"]["live_max_open_positions"], 0)
        self.assertTrue(report["critical_checks"]["execution_order_validated"])
        self.assertEqual(report["paper_autonomy_blockers"], [])
        self.assertIn("alpaca_live_cash_credentials_not_configured", report["live_cash_promotion_blockers"])
        self.assertIn("stage5_90_day_clean_record_not_available", report["live_cash_promotion_blockers"])
        self.assertNotIn("execution_order_has_unresolved_authority_or_risk_fields", report["live_cash_promotion_blockers"])
        self.assertNotIn("live_cash_authority_package_not_validated", report["live_cash_promotion_blockers"])


if __name__ == "__main__":
    unittest.main()
