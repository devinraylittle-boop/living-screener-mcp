from __future__ import annotations

from app.data_adapters.base import MarketDataAdapter
from app.models.schemas import Candle, Quote


class HybridMarketDataAdapter:
    def __init__(self, name: str, quote_adapter: MarketDataAdapter, candle_adapters: list[MarketDataAdapter]):
        self.name = name
        self.quote_adapter = quote_adapter
        self.candle_adapters = candle_adapters
        self.details = {
            "quote_source": quote_adapter.name,
            "candle_sources": [adapter.name for adapter in candle_adapters],
        }

    def get_quote(self, ticker: str) -> Quote | None:
        return self.quote_adapter.get_quote(ticker)

    def get_candles(self, ticker: str, interval: str, period: str) -> list[Candle]:
        for adapter in self.candle_adapters:
            candles = adapter.get_candles(ticker, interval, period)
            if candles:
                return candles
        return []
