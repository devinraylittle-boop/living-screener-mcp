from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

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

    def test_stage4_can_accept_runtime_evidence_and_broker_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = os.fspath(tmp)
            snapshot_path = os.path.join(root, "snapshot.json")
            evidence_path = os.path.join(root, "runtime_evidence.json")
            with open(snapshot_path, "w", encoding="utf-8") as handle:
                json.dump({"positions": [], "open_orders": []}, handle)
            with open(evidence_path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "external_alerting": {
                            "enabled": True,
                            "channels": ["sms"],
                            "last_test_status": "passed",
                            "monitoring_outside_local_machine": True,
                        },
                        "secrets_rotation": {
                            "confirmed": True,
                            "operator_confirmed": True,
                            "live_broker_keys_separated": True,
                            "no_live_secrets_in_package": True,
                        },
                        "monthly_model_review": {"established": True},
                    },
                    handle,
                )

            with patch.dict(
                os.environ,
                {
                    "BROKER_RECONCILIATION_SNAPSHOT_PATH": snapshot_path,
                    "RUNTIME_READINESS_EVIDENCE_PATH": evidence_path,
                },
                clear=False,
            ):
                report = build_report()

        self.assertTrue(report["runtime_checks"]["broker_reconciliation_ready"])
        self.assertTrue(report["runtime_checks"]["external_alerting_ready"])
        self.assertTrue(report["runtime_checks"]["secrets_rotation_confirmed"])
        self.assertIn("paper_promotion_ready", report["runtime_blockers"])


if __name__ == "__main__":
    unittest.main()
