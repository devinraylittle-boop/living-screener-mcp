from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.crypto_paper_service import CryptoPaperRules, CryptoPaperService
from tests.helpers import TempContainer


class CryptoPaperServiceTests(unittest.TestCase):
    def test_start_session_is_paper_only(self) -> None:
        with TempContainer() as container:
            service = CryptoPaperService(container.events)
            result = service.start_session(5, ["BTC-USD"], 8, 15)

        self.assertEqual(result["status"], "PAPER_SESSION_READY")
        self.assertFalse(result["can_place_order_from_this_mcp"])
        self.assertFalse(result["background_worker_started"])

    def test_robinhood_universe_has_all_supported_crypto_in_consideration(self) -> None:
        with TempContainer() as container:
            service = CryptoPaperService(container.events)
            universe = service.universe()

        self.assertEqual(universe["tradable_symbol_count"], 82)
        self.assertEqual(universe["general_consideration_count"], 82)
        self.assertIn("BTC-USD", universe["symbols"])
        self.assertIn("ZORA-USD", universe["symbols"])

    def test_simulator_uses_no_broker_execution(self) -> None:
        with TempContainer() as container:
            service = CryptoPaperService(container.events)

        candles = []
        price = 100.0
        for index in range(40):
            if index >= 20:
                price += 0.2
            candles.append({"timestamp": f"t{index}", "close": price, "volume": 1000 + index * 25})

        result = service._simulate_symbol("BTC-USD", candles, CryptoPaperRules(), 10)

        self.assertEqual(result["status"], "BACKTEST_COMPLETE")
        self.assertEqual(result["starting_cash"], 5.0)
        self.assertGreaterEqual(result["ending_cash"], 0)
        self.assertIn("trade_count", result)

    def test_aggregate_verdict_stays_pass_without_two_positive_symbols(self) -> None:
        with TempContainer() as container:
            service = CryptoPaperService(container.events)

        aggregate = service._aggregate_results(
            [
                {"status": "BACKTEST_COMPLETE", "ending_cash": 5.10, "return_pct": 0.02, "trade_count": 3, "winning_trade_count": 2, "stop_loss_count": 0, "sample_trades": [{"return_pct": 0.01, "exit_reason": "take_profit"}]},
                {"status": "BACKTEST_COMPLETE", "ending_cash": 4.95, "return_pct": -0.01, "trade_count": 3, "winning_trade_count": 1, "stop_loss_count": 3, "sample_trades": [{"return_pct": -0.01, "exit_reason": "stop_loss"}]},
            ],
            5.0,
        )

        self.assertEqual(aggregate["total_trade_count"], 6)
        self.assertEqual(aggregate["positive_symbol_count"], 1)
        self.assertEqual(aggregate["win_rate"], 0.5)
        self.assertEqual(aggregate["stop_loss_frequency"], 0.5)
        self.assertEqual(service._verdict(aggregate), "PASS")

    def test_balanced_profile_relaxes_without_enabling_execution(self) -> None:
        with TempContainer() as container:
            service = CryptoPaperService(container.events)

        rules = service.rules(5.0, {"profile": "balanced"})

        self.assertEqual(rules.starting_cash, 5.0)
        self.assertLess(rules.min_relative_volume, CryptoPaperRules().min_relative_volume)
        self.assertGreater(rules.late_spike_relative_volume, CryptoPaperRules().late_spike_relative_volume)

    def test_symbol_recommendations_separate_carriers_from_leaks(self) -> None:
        with TempContainer() as container:
            service = CryptoPaperService(container.events)

        self.assertEqual(service._symbol_recommendation(2, 5.05, 5.0, 1, {"take_profit": 1, "max_hold": 1}), "PAPER_ELIGIBLE")
        self.assertEqual(service._symbol_recommendation(3, 4.95, 5.0, 1, {"stop_loss": 1, "breakeven_fade": 2}), "LEAK")
        self.assertEqual(service._symbol_recommendation(0, 5.0, 5.0, 0, {}), "NO_TRADE_WATCH")

    def test_downtrend_veto_blocks_long_entries(self) -> None:
        with TempContainer() as container:
            service = CryptoPaperService(container.events)

        candles = []
        price = 100.0
        for index in range(80):
            price -= 0.08
            if index in {35, 55}:
                price += 0.3
            candles.append({"timestamp": f"t{index}", "close": price, "volume": 5000 if index in {35, 55} else 1000})

        result = service._simulate_symbol("ETH-USD", candles, CryptoPaperRules(), 10)

        self.assertEqual(result["trade_count"], 0)

    def test_live_test_gate_passes_when_exchange_proof_is_missing(self) -> None:
        with TempContainer() as container:
            service = CryptoPaperService(container.events)
            fake_backtest = {
                "result": "PAPER_WATCH",
                "best_symbol": "BTC-USD",
                "aggregate": {"total_trade_count": 6, "aggregate_return_pct": 0.01},
                "results": [
                    {
                        "symbol": "BTC-USD",
                        "status": "BACKTEST_COMPLETE",
                        "symbol_recommendation": "PAPER_ELIGIBLE",
                        "trade_count": 4,
                        "win_rate": 0.75,
                        "return_pct": 0.01,
                    }
                ],
            }
            with patch.object(service, "run_backtest", return_value=fake_backtest):
                result = service.live_test_gate(symbols=["BTC-USD"], starting_cash=5.0)

        self.assertEqual(result["final_decision"], "REVIEW_ONLY")
        self.assertEqual(result["exchange_gates"]["status"], "EXCHANGE_PROOF_INCOMPLETE")
        self.assertEqual(result["candidate_classifications"][0]["classification"], "WATCH_ONLY")
        self.assertFalse(result["can_place_order_from_this_mcp"])

    def test_live_test_gate_considers_full_universe_by_default(self) -> None:
        with TempContainer() as container:
            service = CryptoPaperService(container.events)
            fake_backtest = {
                "result": "PASS",
                "best_symbol": None,
                "aggregate": {"total_trade_count": 0, "aggregate_return_pct": 0},
                "results": [],
            }
            with patch.object(service, "run_backtest", return_value=fake_backtest):
                result = service.live_test_gate(backtest_symbol_limit=5)

        self.assertEqual(result["universe"]["general_consideration_count"], 82)
        self.assertEqual(result["universe"]["selected_symbol_count"], 82)
        self.assertEqual(result["universe"]["backtested_symbol_count"], 5)
        self.assertEqual(len(result["candidate_classifications"]), 82)

    def test_live_test_gate_builds_ticket_when_all_crypto_gates_pass(self) -> None:
        with TempContainer() as container:
            service = CryptoPaperService(container.events)
            fake_backtest = {
                "result": "PAPER_WATCH",
                "best_symbol": "BTC-USD",
                "aggregate": {"total_trade_count": 8, "aggregate_return_pct": 0.02},
                "results": [
                    {
                        "symbol": "BTC-USD",
                        "status": "BACKTEST_COMPLETE",
                        "symbol_recommendation": "PAPER_ELIGIBLE",
                        "trade_count": 5,
                        "win_rate": 0.8,
                        "return_pct": 0.02,
                    }
                ],
            }
            with patch.object(service, "run_backtest", return_value=fake_backtest):
                result = service.live_test_gate(
                    symbols=["BTC-USD"],
                    starting_cash=5.0,
                    intended_cash=5.0,
                    account_balance=5.0,
                    buying_power=5.0,
                    exchange_connected=True,
                    open_positions_checked=True,
                    open_position_count=0,
                    open_orders_checked=True,
                    open_order_count=0,
                    market_data_fresh=True,
                    order_book_fresh=True,
                    kill_switch_ready=True,
                    emergency_shutdown_ready=True,
                    daily_loss_lockout_clear=True,
                    fee_bps=2,
                    slippage_pct=0.0002,
                    min_order_size=1.0,
                    target_profit_pct=0.01,
                    stop_loss_pct=0.003,
                    emergency_max_loss=2.0,
                    candidate_snapshots={
                        "BTC-USD": {
                            "bid": 100.00,
                            "ask": 100.05,
                            "volume_24h": 1_000_000_000,
                        }
                    },
                )

        candidate = result["candidate_classifications"][0]
        self.assertEqual(result["final_decision"], "LIMITED_AUTONOMOUS_CRYPTO_ENABLED")
        self.assertEqual(result["risk_controls"]["planned_target_pct"], 0.01)
        self.assertEqual(result["risk_controls"]["planned_trade_max_loss"], 0.015)
        self.assertEqual(result["risk_controls"]["emergency_account_max_loss"], 2.0)
        self.assertEqual(candidate["classification"], "AUTONOMOUS_CRYPTO_APPROVED")
        self.assertEqual(candidate["order_ticket"]["final_verdict"], "AUTONOMOUS_CRYPTO_APPROVED")
        self.assertFalse(candidate["order_ticket"]["can_place_order_from_this_mcp"])

    def test_crypto_live_test_report_summarizes_no_trade_abstention(self) -> None:
        with TempContainer() as container:
            service = CryptoPaperService(container.events)
            report = service.summarize_live_test_report(starting_balance=5.0, ending_balance=5.0)

        self.assertEqual(report["trade_count"], 0)
        self.assertFalse(report["did_force_trades"])
        self.assertEqual(report["final_decision_for_tomorrow"], "REVIEW_ONLY")

    def test_autonomous_cycle_opens_and_manages_paper_position(self) -> None:
        with TempContainer() as container:
            service = CryptoPaperService(container.events)
            fake_gate = {
                "id": 12,
                "final_decision": "LIMITED_AUTONOMOUS_CRYPTO_ENABLED",
                "risk_controls": {"planned_target_pct": 0.01, "planned_stop_loss_pct": 0.003},
                "candidate_classifications": [
                    {
                        "classification": "AUTONOMOUS_CRYPTO_APPROVED",
                        "order_ticket": {
                            "coin_pair": "BTC-USD",
                            "intended_limit_price": 100.0,
                            "mid": 100.0,
                            "ask": 100.0,
                            "position_size": 5.0,
                            "can_place_order_from_this_mcp": False,
                        },
                    }
                ],
            }
            with patch.object(service, "live_test_gate", return_value=fake_gate):
                opened = service.run_autonomous_cycle(symbols=["BTC-USD"], execution_mode="paper")

            with patch.object(service, "live_test_gate", return_value={"final_decision": "NO_TRADE_PLAN", "candidate_classifications": []}):
                closed = service.run_autonomous_cycle(
                    symbols=["BTC-USD"],
                    execution_mode="paper",
                    candidate_snapshots={"BTC-USD": {"bid": 101.2}},
                )

        self.assertEqual(opened["final_decision"], "PAPER_POSITION_OPENED")
        self.assertEqual(opened["new_entry"]["status"], "PAPER_POSITION_OPEN")
        self.assertEqual(closed["management_actions"][0]["action"], "PAPER_CLOSE")
        self.assertEqual(closed["management_actions"][0]["exit_reason"], "target_hit")
        self.assertFalse(opened["can_place_order_from_this_mcp"])

    def test_autonomous_cycle_live_mode_only_hands_off_ticket(self) -> None:
        with TempContainer() as container:
            service = CryptoPaperService(container.events)
            fake_gate = {
                "id": 13,
                "final_decision": "LIMITED_AUTONOMOUS_CRYPTO_ENABLED",
                "risk_controls": {"planned_target_pct": 0.01, "planned_stop_loss_pct": 0.003},
                "candidate_classifications": [
                    {
                        "classification": "AUTONOMOUS_CRYPTO_APPROVED",
                        "order_ticket": {"coin_pair": "BTC-USD", "intended_limit_price": 100.0, "position_size": 5.0},
                    }
                ],
            }
            with patch.object(service, "live_test_gate", return_value=fake_gate):
                result = service.run_autonomous_cycle(symbols=["BTC-USD"], execution_mode="live_handoff")

        self.assertEqual(result["final_decision"], "LIVE_EXECUTOR_HANDOFF_READY")
        self.assertEqual(result["new_entry"]["status"], "LIVE_EXECUTOR_HANDOFF_READY")
        self.assertFalse(result["can_place_order_from_this_mcp"])


if __name__ == "__main__":
    unittest.main()
