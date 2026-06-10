from __future__ import annotations

import unittest

from app.mcp_server import (
    _build_manual_trade_preflight_ticket,
    _close_manual_option_paper_trade,
    _log_manual_option_paper_entry,
    _summarize_manual_option_paper_trades,
    _watch_manual_option_position,
)
from tests.helpers import TempContainer


class PaperOptionLedgerTests(unittest.TestCase):
    def _ready_ticket(self, container) -> dict:
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
            notes="paper-ledger-test",
        )

    def test_entry_close_and_summary_stay_paper_only(self) -> None:
        with TempContainer() as container:
            ticket = self._ready_ticket(container)
            entry = _log_manual_option_paper_entry(
                container,
                ticket,
                fill_price=0.05,
                quantity=1,
                underlying_price=16.2,
                notes="paper entry",
            )
            close = _close_manual_option_paper_trade(
                container,
                entry_id=entry["id"],
                contract_symbol=None,
                exit_price=0.08,
                exit_reason="target_hit",
                notes="paper close",
            )
            summary = _summarize_manual_option_paper_trades(container)

        self.assertEqual(entry["status"], "PAPER_OPTION_ENTRY_OPEN")
        self.assertEqual(entry["entry_debit_dollars"], 5.0)
        self.assertFalse(entry["broker_action"])
        self.assertFalse(entry["can_place_order_from_this_mcp"])
        self.assertEqual(close["status"], "PAPER_OPTION_CLOSED")
        self.assertEqual(close["pnl_dollars"], 3.0)
        self.assertEqual(close["return_pct"], 0.6)
        self.assertIn("classification", close["learning_classification"])
        self.assertFalse(close["order_submitted"])
        self.assertFalse(close["can_cancel_order_from_this_mcp"])
        self.assertEqual(summary["status"], "PAPER_LEDGER_READY")
        self.assertEqual(summary["entry_count"], 1)
        self.assertEqual(summary["closed_count"], 1)
        self.assertEqual(summary["open_count"], 0)
        self.assertEqual(summary["total_pnl_dollars"], 3.0)

    def test_close_missing_entry_returns_safe_noop(self) -> None:
        with TempContainer() as container:
            close = _close_manual_option_paper_trade(
                container,
                entry_id=999,
                contract_symbol=None,
                exit_price=0.08,
                exit_reason="missing",
            )

        self.assertEqual(close["status"], "PAPER_ENTRY_NOT_FOUND")
        self.assertFalse(close["can_place_order_from_this_mcp"])
        self.assertFalse(close["can_cancel_order_from_this_mcp"])

    def test_position_watch_flags_profit_and_stop_without_broker_action(self) -> None:
        with TempContainer() as container:
            ticket = self._ready_ticket(container)
            entry = _log_manual_option_paper_entry(container, ticket, fill_price=0.08, quantity=1, underlying_price=16.2)
            profit = _watch_manual_option_position(
                container,
                entry_id=entry["id"],
                contract_symbol=None,
                current_bid=0.11,
                current_ask=0.13,
                current_mark=None,
                underlying_price=16.0,
                underlying_vwap=16.4,
                notes="profit watch",
            )
            stop = _watch_manual_option_position(
                container,
                entry_id=entry["id"],
                contract_symbol=None,
                current_bid=0.04,
                current_ask=0.05,
                current_mark=None,
                underlying_price=16.6,
                underlying_vwap=16.4,
                notes="stop watch",
            )

        self.assertEqual(profit["status"], "POSITION_PROFIT_REVIEW")
        self.assertEqual(profit["return_pct"], 0.5)
        self.assertEqual(profit["close_request"]["endpoint"], "/paper/options/close")
        self.assertFalse(profit["broker_action"])
        self.assertEqual(stop["status"], "POSITION_STOP_REVIEW")
        self.assertIn("underlying_reclaimed_vwap", stop["close_request"]["exit_reason"])
        self.assertFalse(stop["can_cancel_order_from_this_mcp"])

    def test_position_watch_requires_live_quote(self) -> None:
        with TempContainer() as container:
            ticket = self._ready_ticket(container)
            entry = _log_manual_option_paper_entry(container, ticket, fill_price=0.08, quantity=1, underlying_price=16.2)
            result = _watch_manual_option_position(
                container,
                entry_id=entry["id"],
                contract_symbol=None,
                current_bid=None,
                current_ask=None,
                current_mark=None,
                underlying_price=None,
                underlying_vwap=None,
            )

        self.assertEqual(result["status"], "POSITION_WATCH_NEEDS_LIVE_QUOTE")
        self.assertFalse(result["can_place_order_from_this_mcp"])


if __name__ == "__main__":
    unittest.main()
