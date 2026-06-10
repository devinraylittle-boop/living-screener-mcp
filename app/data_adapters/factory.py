from __future__ import annotations

from app.config import Settings
from app.data_adapters.base import MarketDataAdapter
from app.data_adapters.finnhub_adapter import FinnhubMarketDataAdapter
from app.data_adapters.hybrid_adapter import HybridMarketDataAdapter
from app.data_adapters.mock_adapter import EmptyMarketDataAdapter
from app.data_adapters.polygon_adapter_stub import PolygonMarketDataAdapter
from app.data_adapters.yfinance_adapter import YFinanceMarketDataAdapter


def create_market_data_adapter(settings: Settings) -> MarketDataAdapter | None:
    provider = settings.market_data_provider
    if provider in {"", "none", "disabled", "off"}:
        return None
    if provider == "finnhub":
        if not settings.finnhub_api_key:
            return EmptyMarketDataAdapter()
        finnhub = FinnhubMarketDataAdapter(settings.finnhub_api_key)
        return HybridMarketDataAdapter("finnhub", finnhub, [finnhub, YFinanceMarketDataAdapter()])
    if provider == "yfinance":
        return YFinanceMarketDataAdapter()
    if provider == "polygon":
        return PolygonMarketDataAdapter(settings.polygon_api_key) if settings.polygon_api_key else EmptyMarketDataAdapter()
    return None
