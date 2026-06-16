from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tools.stock_bridge_loop import enforce_live_readiness_gate


class StockBridgeLiveStageGateTests(unittest.TestCase):
    def test_stage_three_live_is_the_only_currently_allowed_live_stage(self) -> None:
        with patch.dict(os.environ, {"AUTONOMY_STAGE": "stage_3_human_approved_live_trades"}, clear=False):
            enforce_live_readiness_gate(live=True)

    def test_stage_five_live_is_refused_even_with_operator_authorization(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AUTONOMY_STAGE": "stage_5_full_autonomous_with_strict_caps",
                "STOCK_BRIDGE_LIVE_AUTH": "ENABLE_AGENTIC_STOCK_BRIDGE",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(SystemExit, "Full or limited autonomous live trading remains blocked"):
                enforce_live_readiness_gate(live=True)

    def test_stage_four_live_is_refused_until_gates_are_satisfied(self) -> None:
        with patch.dict(os.environ, {"AUTONOMY_STAGE": "stage_4_limited_autonomous_live_trades"}, clear=False):
            with self.assertRaisesRegex(SystemExit, "requested stage_4_limited_autonomous_live_trades"):
                enforce_live_readiness_gate(live=True)

    def test_paper_or_dry_run_can_use_requested_stage_without_live_orders(self) -> None:
        with patch.dict(os.environ, {"AUTONOMY_STAGE": "stage_2_paper_trading_automation"}, clear=False):
            enforce_live_readiness_gate(live=False)


if __name__ == "__main__":
    unittest.main()
