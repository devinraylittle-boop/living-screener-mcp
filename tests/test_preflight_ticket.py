from __future__ import annotations

import unittest

from app.mcp_server import _build_manual_trade_preflight_ticket
from tests.helpers import TempContainer


class PreflightTicketTests(unittest.TestCase):
    def test_preflight_ticket_accepts_clean_contract_within_risk_cap(self) -> None:
        with TempContainer() as container:
            result = _build_manual_trade_preflight_ticket(
                container,
                {
                    "ticker": "SOFI",
                    "contract_symbol": "SOFI260612P00015000",
                    "direction": "put",
                    "bid": 0.04,
                    "ask": 0.045,
                    "volume": 500,
                    "open_interest": 2000,
                    "dte": 3,
                    "strike": 15,
                },
                account_value=50,
                max_contract_price=1.0,
                notes="unit-test",
            )

        self.assertEqual(result["event_type"], "manual_preflight_ticket")
        self.assertEqual(result["status"], "MANUAL_PREFLIGHT_READY")
        self.assertEqual(result["option_validation"]["status"], "OPTIONS_CHAIN_ACCEPTABLE")
        self.assertEqual(result["risk_check"]["status"], "APPROVE_FOR_REVIEW")
        self.assertEqual(result["manual_ticket"]["order_type"], "limit_only")
        self.assertEqual(result["manual_ticket"]["quantity"], 1)
        self.assertFalse(result["manual_ticket"]["mcp_can_execute"])
        self.assertFalse(result["can_place_order_from_this_mcp"])

    def test_preflight_ticket_blocks_clean_contract_above_risk_cap(self) -> None:
        with TempContainer() as container:
            result = _build_manual_trade_preflight_ticket(
                container,
                {
                    "ticker": "SOFI",
                    "contract_symbol": "SOFI260612P00015000",
                    "direction": "put",
                    "bid": 0.075,
                    "ask": 0.08,
                    "volume": 500,
                    "open_interest": 2000,
                    "dte": 3,
                    "strike": 15,
                },
                account_value=50,
                max_contract_price=1.0,
            )

        self.assertEqual(result["status"], "NO_TRADE_PLAN")
        self.assertEqual(result["option_validation"]["status"], "OPTIONS_CHAIN_ACCEPTABLE")
        self.assertEqual(result["risk_check"]["status"], "BLOCK")
        self.assertIn("Risk exceeds configured cap.", result["blocking_reasons"])
        self.assertEqual(result["manual_ticket"]["quantity"], 1)
        self.assertFalse(result["can_cancel_order_from_this_mcp"])

    def test_preflight_ticket_blocks_bad_broker_snapshot(self) -> None:
        with TempContainer() as container:
            result = _build_manual_trade_preflight_ticket(
                container,
                {
                    "ticker": "SOFI",
                    "contract_symbol": "SOFI260612P00015000",
                    "direction": "put",
                    "bid": 0.01,
                    "ask": 0.20,
                    "volume": 0,
                    "open_interest": 0,
                    "dte": 0,
                    "strike": 15,
                },
                account_value=50,
                max_contract_price=1.0,
            )

        self.assertEqual(result["status"], "NO_TRADE_PLAN")
        self.assertEqual(result["option_validation"]["status"], "NO_TRADE_PLAN")
        self.assertIn("Broker-visible option snapshot failed options quality validation.", result["blocking_reasons"])
        self.assertEqual(result["manual_ticket"]["quantity"], 0)
        self.assertFalse(result["manual_ticket"]["broker_action_required"])


if __name__ == "__main__":
    unittest.main()
