from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATES_PATH = ROOT / "config" / "autonomous_readiness_gates.json"


class AutonomousReadinessGateTests(unittest.TestCase):
    def test_readiness_gates_are_parseable_and_live_safe(self) -> None:
        gates = json.loads(GATES_PATH.read_text(encoding="utf-8"))

        self.assertFalse(gates["global_live_default"])
        self.assertEqual(gates["classification"], "limited_live_trading_ready")
        self.assertIn("alpaca live cash", gates["scope"].lower())
        self.assertIn("only after", gates["scope"].lower())
        self.assertTrue(gates["required_before_limited_autonomous_live"]["requires_kill_switch"])
        self.assertTrue(gates["required_before_limited_autonomous_live"]["requires_alerting"])
        self.assertTrue(gates["required_before_limited_autonomous_live"]["requires_broker_reconciliation"])

    def test_stage_progression_keeps_live_disabled_until_human_or_gate_control(self) -> None:
        gates = json.loads(GATES_PATH.read_text(encoding="utf-8"))
        stages = gates["stage_limits"]

        self.assertFalse(stages["stage_0_manual_only"]["live_orders"])
        self.assertFalse(stages["stage_1_signal_generation_only"]["live_orders"])
        self.assertFalse(stages["stage_2_paper_trading_automation"]["live_orders"])
        self.assertTrue(stages["stage_3_human_approved_live_trades"]["human_required"])
        self.assertTrue(stages["stage_4_limited_autonomous_live_trades"]["requires_all_gates"])
        self.assertTrue(stages["stage_5_full_autonomous_with_strict_caps"]["requires_external_monitoring"])
        self.assertIn("alpaca_live_cash", stages["stage_5_full_autonomous_with_strict_caps"]["allowed_live_brokers"])

    def test_hard_blocks_include_broker_data_and_loss_controls(self) -> None:
        gates = json.loads(GATES_PATH.read_text(encoding="utf-8"))
        hard_blocks = set(gates["hard_blocks"])

        for required in {
            "missing_or_stale_market_data",
            "broker_review_failure",
            "unreconciled_position_or_order_state",
            "daily_loss_limit_reached",
            "spread_or_quote_age_outside_limits",
            "strategy_not_promoted_from_paper",
            "secrets_or_environment_mismatch",
        }:
            self.assertIn(required, hard_blocks)


if __name__ == "__main__":
    unittest.main()
