from __future__ import annotations

import unittest

from app.mcp_server import _market_phase, _run_trading_day_heartbeat
from tests.helpers import TempContainer


class TradingDayHeartbeatTests(unittest.TestCase):
    def test_force_phase_returns_requested_phase(self) -> None:
        phase = _market_phase("active")

        self.assertEqual(phase["phase"], "active")
        self.assertTrue(phase["forced"])
        self.assertIn("now_utc", phase)

    def test_pending_buy_override_blocks_new_scan_cycle(self) -> None:
        with TempContainer() as container:
            container.events.log(
                "manual_broker_action",
                {
                    "status": "MANUAL_ACTION_PENDING_RECHECK_REQUIRED",
                    "pending_buy": True,
                    "ticker": "SOFI",
                    "review_only": True,
                    "can_place_order_from_this_mcp": False,
                },
            )
            result = _run_trading_day_heartbeat(
                container,
                ["SOFI", "SMCI"],
                account_value=50,
                max_candidates=25,
                review_top_n=8,
                max_contract_price=1.0,
                force_phase="active",
            )

        self.assertEqual(result["status"], "HEARTBEAT_PENDING_RECHECK_REQUIRED")
        self.assertEqual(result["operation"], "pending_recheck_required")
        self.assertEqual(result["next_refresh_seconds"], 60)
        self.assertTrue(result["pending_recheck_required"])
        self.assertFalse(result["can_place_order_from_this_mcp"])
        self.assertFalse(result["broker_action"])


if __name__ == "__main__":
    unittest.main()
