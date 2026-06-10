from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from app.data_adapters.mock_adapter import MockAdapter
from app.mcp_server import _run_market_open_observer
from app.models.schemas import Candle, Quote
from tests.helpers import TempContainer


def quote(ticker: str, price: float) -> Quote:
    return Quote(ticker, price, previous_close=price * 0.97, timestamp=datetime.now(UTC), provider="mock")


def candles(ticker: str, start: float, step: float, count: int = 16, volume: int = 300000) -> list[Candle]:
    base = datetime.now(UTC) - timedelta(minutes=count)
    return [
        Candle(
            ticker,
            base + timedelta(minutes=i),
            start + step * i - 0.05,
            start + step * i + 0.10,
            start + step * i - 0.10,
            start + step * i,
            volume,
            "5m",
            "mock",
        )
        for i in range(count)
    ]


class MarketOpenObserverTests(unittest.TestCase):
    def test_observer_logs_scan_evidence_and_delta(self) -> None:
        with TempContainer() as container:
            container.scanner.market_data = MockAdapter(
                {"NVDA": quote("NVDA", 108), "AAPL": quote("AAPL", 100)},
                {"NVDA": candles("NVDA", 100, 0.60), "AAPL": candles("AAPL", 100, 0.001)},
            )
            first = _run_market_open_observer(container, ["NVDA", "AAPL"], max_candidates=10, cadence_minutes=5)
            second = _run_market_open_observer(container, ["NVDA", "AAPL"], max_candidates=10, cadence_minutes=5)

        self.assertEqual(first["event_type"], "market_open_observer")
        self.assertIn(first["status"], {"OBSERVER_STOCK_CANDIDATES", "OBSERVER_NO_CANDIDATES", "OBSERVER_LOW_CONFIDENCE"})
        self.assertGreaterEqual(first["evidence_packet_count"], 1)
        self.assertIn("evidence_summary", first)
        self.assertFalse(first["can_place_order_from_this_mcp"])
        self.assertFalse(first["broker_action"])
        self.assertEqual(second["delta_vs_previous_observer"]["status"], "OBSERVER_DELTA_READY")
        self.assertIn("observer_refresh", second["action_links"])


if __name__ == "__main__":
    unittest.main()
