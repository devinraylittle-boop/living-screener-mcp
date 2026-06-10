from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
