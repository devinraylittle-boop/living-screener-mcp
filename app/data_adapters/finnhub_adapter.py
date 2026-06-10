from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.models.schemas import Candle, Quote


class FinnhubMarketDataAdapter:
    name = "finnhub"
    base_url = "https://finnhub.io/api/v1"

    def __init__(self, api_key: str, timeout_seconds: int = 15):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def get_quote(self, ticker: str) -> Quote | None:
        try:
            symbol = ticker.upper()
            data = self._get_json("/quote", {"symbol": symbol})
            price = self._float(data.get("c"))
            if price is None or price <= 0:
                return None
            return Quote(
                ticker=symbol,
                price=price,
                previous_close=self._float(data.get("pc")),
                open=self._float(data.get("o")),
                high=self._float(data.get("h")),
                low=self._float(data.get("l")),
                timestamp=self._timestamp(data.get("t")),
                provider=self.name,
            )
        except Exception:
            return None

    def get_candles(self, ticker: str, interval: str, period: str) -> list[Candle]:
        try:
            symbol = ticker.upper()
            end = datetime.now(UTC)
            start = end - self._period_delta(period)
            data = self._get_json(
                "/stock/candle",
                {
                    "symbol": symbol,
                    "resolution": self._resolution(interval),
                    "from": int(start.timestamp()),
                    "to": int(end.timestamp()),
                },
            )
            if data.get("s") != "ok":
                return []
            candles: list[Candle] = []
            for index, raw_time in enumerate(data.get("t", [])):
                candle = self._build_candle(symbol, raw_time, data, index, interval)
                if candle is not None:
                    candles.append(candle)
            return candles
        except Exception:
            return []

    def _get_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        query = dict(params)
        query["token"] = self.api_key
        request = Request(
            f"{self.base_url}{path}?{urlencode(query)}",
            headers={"Accept": "application/json", "User-Agent": "living-screener-mcp/0.2"},
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _build_candle(self, symbol: str, timestamp: Any, data: dict[str, list[Any]], index: int, interval: str) -> Candle | None:
        open_price = self._float(self._at(data.get("o", []), index))
        high = self._float(self._at(data.get("h", []), index))
        low = self._float(self._at(data.get("l", []), index))
        close = self._float(self._at(data.get("c", []), index))
        volume = self._int(self._at(data.get("v", []), index)) or 0
        if any(value is None or value <= 0 for value in [open_price, high, low, close]):
            return None
        return Candle(symbol, self._timestamp(timestamp), open_price, high, low, close, volume, interval, self.name)

    def _resolution(self, interval: str) -> str:
        return {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "1h": "60", "1d": "D"}.get(interval, "5")

    def _period_delta(self, period: str) -> timedelta:
        return {"1d": timedelta(days=1), "5d": timedelta(days=5), "1mo": timedelta(days=31)}.get(period, timedelta(days=5))

    def _timestamp(self, value: Any) -> datetime:
        try:
            raw = int(value)
            if raw > 0:
                return datetime.fromtimestamp(raw, UTC)
        except Exception:
            pass
        return datetime.now(UTC)

    def _at(self, values: list[Any], index: int) -> Any:
        return values[index] if index < len(values) else None

    def _float(self, value: Any) -> float | None:
        try:
            return None if value is None or value != value else float(value)
        except Exception:
            return None

    def _int(self, value: Any) -> int | None:
        try:
            return None if value is None or value != value else int(value)
        except Exception:
            return None
