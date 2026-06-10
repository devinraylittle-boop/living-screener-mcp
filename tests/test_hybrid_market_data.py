from __future__ import annotations

import unittest
from datetime import UTC, datetime

from app.config import Settings
from app.data_adapters.factory import create_market_data_adapter
from app.data_adapters.hybrid_adapter import HybridMarketDataAdapter
from app.models.schemas import Candle, Quote
from tests.helpers import TempContainer


class EmptyCandlesAdapter:
    name = "empty"

    def get_quote(self, ticker: str) -> Quote | None:
        return Quote(ticker.upper(), 100.0, timestamp=datetime.now(UTC), provider=self.name)

    def get_candles(self, ticker: str, interval: str, period: str) -> list[Candle]:
        del ticker, interval, period
        return []


class CandleAdapter:
    name = "fallback"

    def get_quote(self, ticker: str) -> Quote | None:
        del ticker
        return None

    def get_candles(self, ticker: str, interval: str, period: str) -> list[Candle]:
        del period
        return [Candle(ticker.upper(), datetime.now(UTC), 99.0, 101.0, 98.0, 100.0, 1000, interval, self.name)]


class HybridMarketDataTests(unittest.TestCase):
    def test_finnhub_factory_uses_hybrid_adapter_when_key_exists(self) -> None:
        adapter = create_market_data_adapter(Settings(finnhub_api_key="fake", market_data_provider="finnhub"))

        self.assertIsInstance(adapter, HybridMarketDataAdapter)
        self.assertEqual(adapter.name, "finnhub")
        self.assertEqual(adapter.details["quote_source"], "finnhub")
        self.assertIn("yfinance", adapter.details["candle_sources"])

    def test_hybrid_adapter_falls_back_for_candles(self) -> None:
        adapter = HybridMarketDataAdapter("hybrid", EmptyCandlesAdapter(), [EmptyCandlesAdapter(), CandleAdapter()])

        quote = adapter.get_quote("spy")
        candles = adapter.get_candles("spy", "5m", "5d")

        self.assertEqual(quote.provider, "empty")
        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0].provider, "fallback")

    def test_latest_regular_close_handles_monday_premarket(self) -> None:
        with TempContainer() as container:
            close = container.scanner._latest_regular_close(datetime(2026, 6, 8, 12, 0, tzinfo=UTC))

        self.assertEqual(close, datetime(2026, 6, 5, 20, 0, tzinfo=UTC))

    def test_market_open_detection_uses_regular_session(self) -> None:
        with TempContainer() as container:
            self.assertTrue(container.scanner._market_is_regular_open(datetime(2026, 6, 8, 15, 0, tzinfo=UTC)))
            self.assertFalse(container.scanner._market_is_regular_open(datetime(2026, 6, 8, 12, 0, tzinfo=UTC)))
