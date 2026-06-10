from __future__ import annotations

from typing import Protocol

from app.models.schemas import Candle, Quote


class MarketDataAdapter(Protocol):
    name: str

    def get_quote(self, ticker: str) -> Quote | None:
        ...

    def get_candles(self, ticker: str, interval: str, period: str) -> list[Candle]:
        ...
