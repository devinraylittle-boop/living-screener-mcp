from __future__ import annotations

import unittest

from app.mcp_server import (
    _build_manual_trade_preflight_ticket,
    _get_session_risk_guard,
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

    def test_blocks_when_open_positions_and_projected_risk_exceed_caps(self) -> None:
        with TempContainer() as container:
            ticket = self._ticket(container)
            _log_manual_option_paper_entry(container, ticket, fill_price=0.08, quantity=1, underlying_price=16.2)
            _log_manual_option_paper_entry(container, ticket, fill_price=0.08, quantity=1, underlying_price=16.2)
            result = _get_session_risk_guard(container, account_value=50, proposed_risk_dollars=5, max_open_positions=2)

        self.assertEqual(result["status"], "SESSION_RISK_BLOCKED")
        self.assertEqual(result["open_position_count"], 2)
        self.assertIn("Max open paper/manual option positions already reached.", result["blocking_reasons"])
        self.assertFalse(result["broker_action"])

    def test_blocks_after_three_closed_losses_today_without_daily_trade_cap(self) -> None:
        with TempContainer() as container:
            for index in range(2):
                container.events.log(
                    "manual_option_paper_close",
                    {"status": "PAPER_OPTION_CLOSED", "entry_event_id": index + 1, "pnl_dollars": -1.0},
                )
            two_loss_result = _get_session_risk_guard(container, account_value=50, proposed_risk_dollars=1, max_open_positions=2)
            container.events.log(
                "manual_option_paper_close",
                {"status": "PAPER_OPTION_CLOSED", "entry_event_id": 3, "pnl_dollars": -1.0},
            )
            three_loss_result = _get_session_risk_guard(container, account_value=50, proposed_risk_dollars=1, max_open_positions=2)

        self.assertNotEqual(two_loss_result["status"], "SESSION_RISK_BLOCKED")
        self.assertEqual(two_loss_result["daily_loss_count"], 2)
        self.assertEqual(three_loss_result["status"], "SESSION_RISK_BLOCKED")
        self.assertEqual(three_loss_result["daily_loss_count"], 3)
        self.assertEqual(three_loss_result["daily_loss_lockout_count"], 3)
        self.assertTrue(three_loss_result["daily_loss_lockout_triggered"])
        self.assertIn("There is no hard daily trade-count cap for review/paper research.", three_loss_result["rules"])
        self.assertIn("Daily closed-loss lockout reached (3/3 losses).", three_loss_result["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()
