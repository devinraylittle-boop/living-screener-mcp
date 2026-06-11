from __future__ import annotations

import unittest

from app.mcp_server import _build_manual_trade_desk, _log_manual_broker_action
from tests.helpers import TempContainer


class ManualTradeDeskTests(unittest.TestCase):
    def test_manual_trade_desk_prepares_paper_entry_for_clean_snapshot(self) -> None:
        with TempContainer() as container:
            result = _build_manual_trade_desk(
                container,
                {
                    "ticker": "SOFI",
                    "contract_symbol": "SOFI260612P00015000",
                    "direction": "put",
                    "underlying_price": 16.5,
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

        self.assertEqual(result["event_type"], "manual_trade_desk")
        self.assertEqual(result["status"], "MANUAL_TRADE_DESK_READY")
        self.assertEqual(result["preflight"]["status"], "MANUAL_PREFLIGHT_READY")
        self.assertEqual(result["session_risk_guard"]["status"], "SESSION_RISK_CLEAR")
        self.assertEqual(result["session_risk_guard"]["proposed_risk_dollars"], 4.5)
        self.assertEqual(result["blocking_reasons"], [])
        self.assertEqual(result["paper_entry_request"]["endpoint"], "/paper/options/entry")
        self.assertEqual(result["paper_entry_request"]["payload"]["fill_price"], 0.045)
        self.assertEqual(result["paper_entry_request"]["payload"]["underlying_price"], 16.5)
        self.assertEqual(result["checkpoint_request"]["endpoint"], "/journal/checkpoint?limit=500&format=json")
        self.assertFalse(result["can_place_order_from_this_mcp"])
        self.assertFalse(result["can_cancel_order_from_this_mcp"])
        self.assertFalse(result["order_submitted"])
        self.assertFalse(result["broker_action"])

    def test_manual_trade_desk_blocks_bad_snapshot_without_paper_payload(self) -> None:
        with TempContainer() as container:
            result = _build_manual_trade_desk(
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
        self.assertEqual(result["preflight"]["status"], "NO_TRADE_PLAN")
        self.assertIsNone(result["paper_entry_request"])
        self.assertIn("Broker-visible option snapshot failed options quality validation.", result["preflight"]["blocking_reasons"])
        self.assertFalse(result["order_placed"])
        self.assertFalse(result["order_submitted"])
        self.assertFalse(result["broker_action"])

    def test_manual_trade_desk_blocks_after_real_cash_daily_loss_lockout(self) -> None:
        snapshot = {
            "ticker": "SOFI",
            "contract_symbol": "SOFI260612P00015000",
            "direction": "put",
            "underlying_price": 16.5,
            "bid": 0.04,
            "ask": 0.045,
            "volume": 500,
            "open_interest": 2000,
            "dte": 3,
            "strike": 15,
        }
        with TempContainer() as container:
            for index in range(3):
                _log_manual_broker_action(
                    container,
                    {
                        "ticker": "SOFI",
                        "contract_symbol": f"SOFI260612P0001500{index}",
                        "action_type": "sell_to_close",
                        "order_status": "filled",
                        "side": "sell",
                        "direction": "put",
                        "fill_price": 0.04,
                        "quantity": 1,
                        "pnl_dollars": -1.0,
                        "is_real_cash": True,
                    },
                )
            result = _build_manual_trade_desk(
                container,
                snapshot,
                account_value=50,
                max_contract_price=1.0,
                max_open_positions=2,
            )

        self.assertEqual(result["status"], "NO_TRADE_PLAN")
        self.assertEqual(result["preflight"]["status"], "MANUAL_PREFLIGHT_READY")
        self.assertEqual(result["session_risk_guard"]["status"], "SESSION_RISK_BLOCKED")
        self.assertIsNone(result["paper_entry_request"])
        self.assertIn("Session risk guard: Real-cash daily closed-loss lockout reached (3/3 losses).", result["blocking_reasons"])
        self.assertFalse(result["broker_action"])


if __name__ == "__main__":
    unittest.main()
