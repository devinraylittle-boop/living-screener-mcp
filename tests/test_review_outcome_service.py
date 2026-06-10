from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from app.data_adapters.mock_adapter import MockAdapter
from app.models.schemas import Candle, Quote
from app.services.review_outcome_service import ReviewOutcomeService
from tests.helpers import TempContainer


def candles(ticker: str, prices: list[float]) -> list[Candle]:
    base = datetime.now(UTC) - timedelta(minutes=len(prices))
    return [
        Candle(ticker, base + timedelta(minutes=index), price - 0.05, price + 0.10, price - 0.10, price, 100000, "5m", "mock")
        for index, price in enumerate(prices)
    ]


def candles_at(ticker: str, start: datetime, prices: list[float]) -> list[Candle]:
    return [
        Candle(ticker, start + timedelta(minutes=5 * index), price - 0.05, price + 0.10, price - 0.10, price, 100000, "5m", "mock")
        for index, price in enumerate(prices)
    ]


class ReviewOutcomeServiceTests(unittest.TestCase):
    def test_short_review_benefits_when_price_falls(self) -> None:
        with TempContainer() as container:
            container.market_data = MockAdapter(
                {"SOFI": Quote("SOFI", 15.80, previous_close=16.20, timestamp=datetime.now(UTC), provider="mock")},
                {"SOFI": candles("SOFI", [16.0, 15.95, 15.90, 15.85, 15.80])},
            )
            service = ReviewOutcomeService(container.settings, container.events, container.market_data)

            result = service.check_review_outcome({"ticker": "SOFI", "direction": "put", "entry_reference": 16.0})

        self.assertEqual(result["verdict"], "HELPED")
        self.assertGreater(result["current_return_pct"], 0)
        self.assertEqual(result["outcome_window_status"], "UNANCHORED_REVIEW_TIME")
        self.assertIsNone(result["horizon_returns"]["15m"])
        self.assertFalse(result["can_place_order_from_this_mcp"])

    def test_long_review_hurts_when_price_falls(self) -> None:
        with TempContainer() as container:
            container.market_data = MockAdapter(
                {"UNH": Quote("UNH", 390.0, previous_close=395.0, timestamp=datetime.now(UTC), provider="mock")},
                {"UNH": candles("UNH", [395, 394, 393, 392, 390])},
            )
            service = ReviewOutcomeService(container.settings, container.events, container.market_data)

            result = service.check_review_outcome({"ticker": "UNH", "direction": "call", "entry_reference": 395.0})

        self.assertEqual(result["verdict"], "HURT")
        self.assertLess(result["current_return_pct"], 0)

    def test_review_timestamp_anchors_horizon_returns_after_decision(self) -> None:
        review_time = datetime.now(UTC) - timedelta(minutes=20)
        all_candles = candles_at("SOFI", review_time - timedelta(minutes=10), [16.80, 16.70, 16.00, 15.90, 15.80, 15.70])
        with TempContainer() as container:
            container.market_data = MockAdapter(
                {"SOFI": Quote("SOFI", 15.70, previous_close=16.20, timestamp=datetime.now(UTC), provider="mock")},
                {"SOFI": all_candles},
            )
            service = ReviewOutcomeService(container.settings, container.events, container.market_data)

            result = service.check_review_outcome(
                {
                    "ticker": "SOFI",
                    "direction": "put",
                    "entry_reference": 16.0,
                    "review_timestamp": review_time.isoformat(),
                },
                {"15m": 3},
            )

        self.assertEqual(result["outcome_window_status"], "ANCHORED_TO_REVIEW_TIMESTAMP")
        self.assertEqual(result["horizon_returns"]["15m"], 0.0125)

    def test_summary_aggregates_outcomes(self) -> None:
        with TempContainer() as container:
            service = ReviewOutcomeService(container.settings, container.events, None)
            result = service.summarize_review_outcomes(
                [
                    {"ticker": "A", "current_return_pct": 0.01},
                    {"ticker": "B", "current_return_pct": -0.005},
                ]
            )

        self.assertEqual(result["sample_size"], 2)
        self.assertEqual(result["win_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
