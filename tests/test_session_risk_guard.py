from __future__ import annotations

import unittest

from app.mcp_server import (
    _build_manual_trade_preflight_ticket,
    _get_session_risk_guard,
    _log_manual_broker_action,
    _log_manual_option_paper_entry,
)
from tests.helpers import TempContainer


class SessionRiskGuardTests(unittest.TestCase):
    def _ticket(self, container) -> dict:
        return _build_manual_trade_preflight_ticket(
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
            notes="session-risk-test",
        )

    def test_clear_when_no_open_risk_and_proposed_within_cap(self) -> None:
        with TempContainer() as container:
            result = _get_session_risk_guard(container, account_value=50, proposed_risk_dollars=5, max_open_positions=2)

        self.assertEqual(result["status"], "SESSION_RISK_CLEAR")
        self.assertEqual(result["per_trade_cap_dollars"], 5.0)
        self.assertEqual(result["projected_open_risk_dollars"], 5.0)
        self.assertFalse(result["can_place_order_from_this_mcp"])

    def test_paper_open_positions_do_not_block_research(self) -> None:
        with TempContainer() as container:
            ticket = self._ticket(container)
            _log_manual_option_paper_entry(container, ticket, fill_price=0.08, quantity=1, underlying_price=16.2)
            _log_manual_option_paper_entry(container, ticket, fill_price=0.08, quantity=1, underlying_price=16.2)
            result = _get_session_risk_guard(container, account_value=50, proposed_risk_dollars=5, max_open_positions=2)

        self.assertEqual(result["status"], "SESSION_RISK_CLEAR")
        self.assertEqual(result["open_position_count"], 2)
        self.assertEqual(result["paper_open_position_count"], 2)
        self.assertEqual(result["real_cash_open_position_count"], 0)
        self.assertEqual(result["blocking_reasons"], [])
        self.assertFalse(result["broker_action"])

    def test_paper_closed_losses_do_not_trigger_daily_cash_lockout(self) -> None:
        with TempContainer() as container:
            for index in range(3):
                container.events.log(
                    "manual_option_paper_close",
                    {"status": "PAPER_OPTION_CLOSED", "entry_event_id": index + 1, "pnl_dollars": -1.0},
                )
            result = _get_session_risk_guard(container, account_value=50, proposed_risk_dollars=1, max_open_positions=2)

        self.assertEqual(result["status"], "SESSION_RISK_CLEAR")
        self.assertEqual(result["paper_daily_loss_count"], 3)
        self.assertEqual(result["real_cash_daily_loss_count"], 0)
        self.assertFalse(result["real_cash_daily_loss_lockout_triggered"])
        self.assertIn("Paper/research scanning, paper entries, and paper closes are uncapped for learning.", result["rules"])

    def test_blocks_after_three_real_cash_closed_losses_today(self) -> None:
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
            result = _get_session_risk_guard(container, account_value=50, proposed_risk_dollars=1, max_open_positions=2)

        self.assertEqual(result["status"], "SESSION_RISK_BLOCKED")
        self.assertEqual(result["real_cash_daily_loss_count"], 3)
        self.assertEqual(result["real_cash_daily_loss_lockout_count"], 3)
        self.assertTrue(result["real_cash_daily_loss_lockout_triggered"])
        self.assertIn("Real-cash daily closed-loss lockout reached (3/3 losses).", result["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()
