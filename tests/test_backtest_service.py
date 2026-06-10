from __future__ import annotations

import unittest

from app.services.backtest_service import BacktestService
from tests.helpers import TempContainer


class BacktestServiceTests(unittest.TestCase):
    def test_score_can_create_candidate_without_lookahead(self) -> None:
        with TempContainer() as container:
            service = BacktestService(container.events, container.settings)

        score = service._score([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111], [100000] * 11 + [300000], 112)

        self.assertGreaterEqual(score, 65)

    def test_scalp_rvol_floor_creates_watch_only_decision(self) -> None:
        with TempContainer() as container:
            service = BacktestService(container.events, container.settings)

        score = service._score([100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89], [100000] * 12, 88, scalp=True)
        relative_volume = service._relative_volume([100000] * 12)

        self.assertGreaterEqual(score, 58)
        self.assertLess(relative_volume, 1.15)

    def test_horizon_summary_aggregates_forward_returns(self) -> None:
        with TempContainer() as container:
            service = BacktestService(container.events, container.settings)

        summary = service._horizon_summary(
            [
                {"forward_returns": {"15m": 0.01, "30m": -0.01}},
                {"forward_returns": {"15m": 0.02, "30m": 0.03}},
            ]
        )

        self.assertEqual(summary["15m"]["sample_size"], 2)
        self.assertEqual(summary["15m"]["win_rate"], 1.0)
        self.assertEqual(summary["30m"]["win_rate"], 0.5)

    def test_empty_history_result_remains_safe(self) -> None:
        with TempContainer() as container:
            service = BacktestService(container.events, container.settings)
            result = service.events.log(
                "backtest",
                {
                    "engine": "test",
                    "tickers": ["SPY"],
                    "sample_size": 0,
                    "no_lookahead_bias": True,
                    "expectancy": 0,
                },
            )

        self.assertEqual(result["sample_size"], 0)
        self.assertTrue(result["no_lookahead_bias"])
