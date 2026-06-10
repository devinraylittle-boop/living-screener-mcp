from __future__ import annotations

from app.models.schemas import Candle, Quote


class PolygonMarketDataAdapter:
    name = "polygon"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    def get_quote(self, ticker: str) -> Quote | None:
        del ticker
        return None

    def get_candles(self, ticker: str, interval: str, period: str) -> list[Candle]:
        del ticker, interval, period
        return []
