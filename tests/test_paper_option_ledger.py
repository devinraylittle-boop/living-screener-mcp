from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from app.mcp_server import (
    _build_manual_trade_preflight_ticket,
    _close_manual_option_paper_trade,
    _log_manual_option_paper_entry,
    _run_paper_exploration,
    _run_paper_exploration_followup,
    _summarize_paper_exploration,
    _summarize_manual_option_paper_trades,
    _watch_manual_option_position,
)
from tests.helpers import TempContainer

from app.data_adapters.mock_adapter import MockAdapter
from app.models.schemas import Candle, Quote


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
        self.assertEqual(close["outcome_record_v2"]["schema_version"], "OutcomeRecordV2")
        self.assertEqual(close["signal_outcome_label"], "SIGNAL_HELPED")
        self.assertEqual(close["execution_outcome_label"], "EXECUTION_WORSE_THAN_REVIEW")
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

    def test_paper_exploration_opens_tagged_trials_without_cash_permission(self) -> None:
        now = datetime.now(UTC)
        quote_obj = Quote("NVDA", 110, previous_close=100, timestamp=now, provider="mock")
        candle_list = [
            Candle("NVDA", now - timedelta(minutes=16 - i), 100 + i * 0.7, 101 + i * 0.7, 99 + i * 0.7, 100 + i * 0.7, 500000, "5m", "mock")
            for i in range(16)
        ]
        with TempContainer() as container:
            container.scanner.market_data = MockAdapter({"NVDA": quote_obj}, {"NVDA": candle_list})
            result = _run_paper_exploration(
                container,
                ["NVDA"],
                max_candidates=5,
                max_trials=3,
                max_contract_price=2.0,
                include_passes=True,
                exploration_level="aggressive",
            )
            summary = _summarize_paper_exploration(container)
            followup = _run_paper_exploration_followup(container, limit_runs=1, max_items=5, classify=True)

        self.assertIn(result["status"], {"PAPER_EXPLORATION_TRIALS_OPENED", "PAPER_EXPLORATION_NO_ENTRIES"})
        self.assertFalse(result["cash_gate_status"]["cash_gates_changed"])
        self.assertFalse(result["can_place_order_from_this_mcp"])
        self.assertTrue(result["paper_only"])
        for trial in result["trials"]:
            if trial["status"] == "PAPER_EXPLORATION_ENTRY_OPENED":
                self.assertGreater(trial["underlying_entry_reference"], 0)
        self.assertEqual(summary["status"], "PAPER_EXPLORATION_SUMMARY_READY")
        self.assertFalse(summary["cash_gate_status"]["real_money_allowed_from_this_output"])
        self.assertIn(followup["status"], {"PAPER_EXPLORATION_FOLLOWUP_READY", "PAPER_EXPLORATION_FOLLOWUP_WAITING"})
        self.assertFalse(followup["broker_action"])


if __name__ == "__main__":
    unittest.main()
