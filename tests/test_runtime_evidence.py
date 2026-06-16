from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.runtime_evidence import build_runtime_evidence_report


class RuntimeEvidenceTests(unittest.TestCase):
    def test_missing_runtime_evidence_blocks_readiness(self) -> None:
        report = build_runtime_evidence_report(Path("missing-runtime-evidence.json"))

        self.assertEqual(report["status"], "RUNTIME_EVIDENCE_BLOCKED")
        self.assertFalse(report["external_alerting_ready"])
        self.assertFalse(report["secrets_rotation_ready"])
        self.assertFalse(report["monthly_model_review_ready"])
        self.assertIn("evidence_file_readable", report["blockers"])

    def test_complete_runtime_evidence_can_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime_evidence.json"
            path.write_text(
                json.dumps(
                    {
                        "external_alerting": {
                            "enabled": True,
                            "channels": ["sms"],
                            "last_test_at": "2026-06-16T15:00:00-05:00",
                            "last_test_status": "passed",
                            "monitoring_outside_local_machine": True,
                        },
                        "secrets_rotation": {
                            "confirmed": True,
                            "operator_confirmed": True,
                            "rotated_at": "2026-06-16T15:00:00-05:00",
                            "live_broker_keys_separated": True,
                            "no_live_secrets_in_package": True,
                        },
                        "monthly_model_review": {
                            "established": True,
                            "next_due": "2026-07-16",
                        },
                    }
                ),
                encoding="utf-8",
            )

            report = build_runtime_evidence_report(path)

        self.assertEqual(report["status"], "RUNTIME_EVIDENCE_READY")
        self.assertTrue(report["external_alerting_ready"])
        self.assertTrue(report["secrets_rotation_ready"])
        self.assertTrue(report["monthly_model_review_ready"])
        self.assertEqual(report["blockers"], [])


if __name__ == "__main__":
    unittest.main()
