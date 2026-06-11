from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.models.schemas import Candle, Quote
from app.services.market_truth_service import MarketTruthService
from tests.helpers import TempContainer


class FakeMarketData:
    name = "fake"

    def __init__(self, healthy: bool = True):
        self.healthy = healthy

    def get_quote(self, ticker: str) -> Quote | None:
        if not self.healthy:
            return None
        return Quote(
            ticker=ticker,
            price=10.0,
            previous_close=9.8,
            timestamp=datetime.now(UTC) - timedelta(seconds=10),
            provider=self.name,
        )

    def get_candles(self, ticker: str, interval: str, period: str) -> list[Candle]:
        if not self.healthy:
            return []
        now = datetime.now(UTC)
        return [
            Candle(
                ticker=ticker,
                timestamp=now - timedelta(minutes=index),
                open=9.8,
                high=10.1,
                low=9.7,
                close=10.0,
                volume=1000,
                interval=interval,
                provider=self.name,
            )
            for index in range(390, 0, -1)
        ]


class MarketTruthServiceTests(unittest.TestCase):
    def test_truth_source_status_is_review_only_and_cash_blocked_by_default(self) -> None:
        with TempContainer() as container:
            service = MarketTruthService(container.settings, container.events, None, container.options)
            result = service.truth_source_status()

        self.assertEqual(result["schema_version"], "truth_source_status_v1")
        self.assertFalse(result["cash_readiness"]["cash_ready"])
        self.assertFalse(result["can_place_order_from_this_mcp"])
        self.assertIn("fresh catalyst context", result["blocked_for_cash_without"])

    def test_market_data_health_accepts_fresh_quote_and_candles(self) -> None:
        with TempContainer() as container:
            service = MarketTruthService(container.settings, container.events, FakeMarketData(), container.options)
            result = service.check_market_data_health(["SOFI"], 1)

        self.assertEqual(result["schema_version"], "market_data_health_v1")
        self.assertEqual(result["status"], "MARKET_DATA_HEALTHY")
        self.assertTrue(result["cash_ready"])
        self.assertEqual(result["rows"][0]["status"], "HEALTHY")

    def test_market_data_health_fails_closed_without_adapter(self) -> None:
        with TempContainer() as container:
            service = MarketTruthService(container.settings, container.events, None, container.options)
            result = service.check_market_data_health(["SOFI"], 1)

        self.assertEqual(result["status"], "MARKET_DATA_HEALTH_BLOCKED")
        self.assertFalse(result["cash_ready"])
        self.assertEqual(result["rows"][0]["status"], "NO_ADAPTER")

    def test_catalyst_context_fails_closed_without_finnhub_key(self) -> None:
        with TempContainer() as container:
            settings = replace(container.settings, finnhub_api_key="")
            service = MarketTruthService(settings, container.events, None, container.options)
            result = service.get_catalyst_context("SOFI")

        self.assertEqual(result["schema_version"], "catalyst_context_v1")
        self.assertEqual(result["status"], "CATALYST_CONTEXT_UNAVAILABLE")
        self.assertFalse(result["cash_ready"])
        self.assertIn("FINNHUB_API_KEY missing; catalyst context cannot be trusted.", result["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()
