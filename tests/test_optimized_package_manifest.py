from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "config" / "optimized_package_manifest.json"


class OptimizedPackageManifestTests(unittest.TestCase):
    def test_manifest_is_parseable_and_safe_by_default(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertEqual(manifest["readiness"], "limited_live_trading_ready")
        self.assertEqual(manifest["safe_default_stage"], "stage_2_paper_trading_automation")
        self.assertEqual(manifest["maximum_current_live_stage"], "stage_3_human_approved_live_trades")
        self.assertEqual(manifest["full_autonomous_live_stage"], "blocked_until_readiness_gates_pass")

    def test_manifest_excludes_runtime_noise(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        excluded = set(manifest["excluded_runtime_noise"])

        for expected in {
            "__pycache__",
            ".pytest_cache",
            "*.pyc",
            "data/stock_bridge_loop.jsonl",
            "data/stock_bridge_state.json",
            "data/paper_lifecycle_ledger.jsonl",
            "data/stock_bridge_*.out.log",
            "data/stock_bridge_*.err.log",
            "sqlite_runtime_databases",
            "local_env_files",
        }:
            self.assertIn(expected, excluded)

    def test_stage_four_prerequisites_are_explicit(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        required = set(manifest["required_next_build_items_for_stage_4"])

        for expected in {
            "paper_lifecycle_ledger",
            "broker_reconciliation_service",
            "external_alerting",
            "runtime_readiness_evidence_file",
            "operator_kill_switch",
            "minimum_paper_sample_size",
            "walk_forward_validation",
        }:
            self.assertIn(expected, required)


if __name__ == "__main__":
    unittest.main()
