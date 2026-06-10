from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models.schemas import Candle, Quote


class YFinanceMarketDataAdapter:
    name = "yfinance"

    def get_quote(self, ticker: str) -> Quote | None:
        try:
            yf = self._load_yfinance()
            symbol = ticker.upper()
            history = yf.Ticker(symbol).history(period="2d", interval="1m", prepost=False)
            if history is None or history.empty:
                return None
            last = history.iloc[-1]
            price = self._float(last.get("Close"))
            if price is None or price <= 0:
                return None
            return Quote(
                ticker=symbol,
                price=price,
                previous_close=self._previous_session_close(history),
                open=self._float(last.get("Open")),
                high=self._float(last.get("High")),
                low=self._float(last.get("Low")),
                volume=self._int(last.get("Volume")),
                timestamp=self._to_datetime(history.index[-1]),
                provider=self.name,
            )
        except Exception:
            return None

    def get_candles(self, ticker: str, interval: str, period: str) -> list[Candle]:
        try:
            yf = self._load_yfinance()
            symbol = ticker.upper()
            history = yf.Ticker(symbol).history(period=period, interval=interval, prepost=False)
            if history is None or history.empty:
                return []
            candles = []
            for timestamp, row in history.iterrows():
                candle = self._row_to_candle(symbol, timestamp, row, interval)
                if candle is not None:
                    candles.append(candle)
            return candles
        except Exception:
            return []

    def _load_yfinance(self) -> Any:
        import yfinance as yf

        return yf

    def _row_to_candle(self, ticker: str, timestamp: Any, row: Any, interval: str) -> Candle | None:
        open_price = self._float(row.get("Open"))
        high = self._float(row.get("High"))
        low = self._float(row.get("Low"))
        close = self._float(row.get("Close"))
        volume = self._int(row.get("Volume")) or 0
        if any(value is None or value <= 0 for value in [open_price, high, low, close]):
            return None
        return Candle(ticker, self._to_datetime(timestamp), open_price, high, low, close, volume, interval, self.name)

    def _to_datetime(self, value: Any) -> datetime:
        if hasattr(value, "to_pydatetime"):
            value = value.to_pydatetime()
        if isinstance(value, datetime):
            return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
        return datetime.now(UTC)

    def _previous_session_close(self, history: Any) -> float | None:
        if history is None or history.empty:
            return None
        try:
            latest_date = history.index[-1].date()
            previous_rows = history[[timestamp.date() < latest_date for timestamp in history.index]]
            if previous_rows is not None and not previous_rows.empty:
                return self._float(previous_rows.iloc[-1].get("Close"))
        except Exception:
            pass
        try:
            if len(history) > 1:
                return self._float(history.iloc[-2].get("Close"))
        except Exception:
            pass
        return None

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
