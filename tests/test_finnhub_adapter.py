from __future__ import annotations

import unittest
from datetime import UTC, datetime

from app.data_adapters.finnhub_adapter import FinnhubMarketDataAdapter


class FakeFinnhubAdapter(FinnhubMarketDataAdapter):
    def __init__(self, responses: dict[str, dict]):
        super().__init__("fake")
        self.responses = responses

    def _get_json(self, path: str, params: dict) -> dict:
        return self.responses[path]


class FinnhubAdapterTests(unittest.TestCase):
    def test_parses_quote_and_candles(self) -> None:
        ts = int(datetime(2026, 1, 1, tzinfo=UTC).timestamp())
        adapter = FakeFinnhubAdapter({
            "/quote": {"c": 101.0, "pc": 100.0, "o": 100.5, "h": 102.0, "l": 99.0, "t": ts},
            "/stock/candle": {"s": "ok", "t": [ts, ts + 300], "o": [100, 101], "h": [101, 102], "l": [99, 100], "c": [100.5, 101.5], "v": [1000, 2000]},
        })

        quote = adapter.get_quote("spy")
        candles = adapter.get_candles("spy", "5m", "1d")

        self.assertEqual(quote.ticker, "SPY")
        self.assertEqual(quote.price, 101.0)
        self.assertEqual(len(candles), 2)

    def test_provider_errors_fail_safely(self) -> None:
        class Broken(FinnhubMarketDataAdapter):
            def _get_json(self, path: str, params: dict) -> dict:
                raise RuntimeError("down")

        adapter = Broken("fake")
        self.assertIsNone(adapter.get_quote("SPY"))
        self.assertEqual(adapter.get_candles("SPY", "5m", "1d"), [])
