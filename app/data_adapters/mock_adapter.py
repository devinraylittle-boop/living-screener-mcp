from __future__ import annotations

from app.models.schemas import Candle, Quote


class EmptyMarketDataAdapter:
    name = "none"

    def get_quote(self, ticker: str) -> Quote | None:
        del ticker
        return None

    def get_candles(self, ticker: str, interval: str, period: str) -> list[Candle]:
        del ticker, interval, period
        return []


class MockAdapter:
    name = "mock"

    def __init__(self, quotes: dict[str, Quote | None] | None = None, candles: dict[str, list[Candle]] | None = None):
        self.quotes = {key.upper(): value for key, value in (quotes or {}).items()}
        self.candles = {key.upper(): value for key, value in (candles or {}).items()}

    def get_quote(self, ticker: str) -> Quote | None:
        return self.quotes.get(ticker.upper())

    def get_candles(self, ticker: str, interval: str, period: str) -> list[Candle]:
        del interval, period
        return self.candles.get(ticker.upper(), [])
