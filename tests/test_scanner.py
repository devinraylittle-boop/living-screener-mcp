from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from app.data_adapters.mock_adapter import MockAdapter
from app.models.schemas import Candle, Quote
from tests.helpers import TempContainer


def quote(ticker: str, price: float, timestamp=None) -> Quote:
    return Quote(ticker, price, previous_close=price * 0.97, timestamp=timestamp or datetime.now(UTC), provider="mock")


def candles(ticker: str, start: float, step: float, count: int = 12, volume: int = 250000) -> list[Candle]:
    base = datetime.now(UTC) - timedelta(minutes=count)
    return [Candle(ticker, base + timedelta(minutes=i), start + step * i - .05, start + step * i + .1, start + step * i - .1, start + step * i, volume, "5m", "mock") for i in range(count)]


class QuoteFailingAdapter(MockAdapter):
    def get_quote(self, ticker: str) -> Quote | None:
        del ticker
        raise RuntimeError("quote provider down")


class ScannerTests(unittest.TestCase):
    def test_no_adapter_returns_pass(self) -> None:
        with TempContainer() as container:
            result = container.scanner.run_market_scan("conservative_review_only", ["SPY"])
        self.assertEqual(result["data_provider"], "none")
        self.assertEqual(result["top_candidates"], [])
        self.assertIn("No live market data adapter configured.", result["pass_list"][0]["reasons"])

    def test_missing_quote_uses_fresh_candle_derived_quote(self) -> None:
        with TempContainer() as container:
            container.scanner.market_data = MockAdapter({"SPY": None}, {"SPY": candles("SPY", 100, 1)})
            result = container.scanner.run_market_scan("day_trade", ["SPY"])
        self.assertGreater(len(result["top_candidates"]), 0)
        self.assertTrue(result["top_candidates"][0]["quote_summary"]["derived_from_candles"])
        self.assertEqual(result["top_candidates"][0]["quote_summary"]["previous_close_source"], "prior_candle_close")

    def test_quote_provider_failure_can_still_use_candle_derived_quote(self) -> None:
        with TempContainer() as container:
            container.scanner.market_data = QuoteFailingAdapter({}, {"SPY": candles("SPY", 100, 1)})
            result = container.scanner.run_market_scan("day_trade", ["SPY"])

        self.assertGreater(len(result["top_candidates"]), 0)
        candidate = result["top_candidates"][0]
        self.assertTrue(candidate["quote_summary"]["derived_from_candles"])
        self.assertIn("quote was derived", " ".join(candidate["reasons"]).lower())

    def test_missing_quote_with_stale_candles_still_returns_pass(self) -> None:
        old = datetime.now(UTC) - timedelta(days=3)
        stale_candles = [Candle("SPY", old + timedelta(minutes=i), 100 + i, 100.1 + i, 99.9 + i, 100 + i, 250000, "5m", "mock") for i in range(12)]
        with TempContainer() as container:
            container.scanner.market_data = MockAdapter({"SPY": None}, {"SPY": stale_candles})
            result = container.scanner.run_market_scan("day_trade", ["SPY"])
        self.assertEqual(result["top_candidates"], [])
        self.assertIn("Quote missing", " ".join(result["pass_list"][0]["reasons"]))

    def test_stale_data_returns_pass(self) -> None:
        old = datetime.now(UTC) - timedelta(days=3)
        with TempContainer() as container:
            container.scanner.market_data = MockAdapter({"SPY": quote("SPY", 100, old)}, {"SPY": candles("SPY", 100, 1)})
            result = container.scanner.run_market_scan("day_trade", ["SPY"])
        self.assertEqual(result["top_candidates"], [])
        self.assertIn("stale", " ".join(result["pass_list"][0]["reasons"]).lower())

    def test_valid_uptrend_can_score_candidate(self) -> None:
        with TempContainer() as container:
            container.scanner.market_data = MockAdapter({"SPY": quote("SPY", 112)}, {"SPY": candles("SPY", 100, 1)})
            result = container.scanner.run_market_scan("day_trade", ["SPY"])
        self.assertGreater(len(result["top_candidates"]), 0)
        candidate = result["top_candidates"][0]
        self.assertTrue(candidate["review_only"])
        self.assertFalse(candidate["order_allowed"])
        self.assertIn("key_signals", candidate)
        self.assertEqual(candidate["quality_gates"]["stock_setup_quality"], "VALID_CANDIDATE")
        self.assertEqual(candidate["quality_gates"]["options_chain_quality"], "NOT_VALIDATED")
        self.assertIn("freshness_status", candidate["quote_summary"])
        self.assertEqual(candidate["key_signals"]["relative_volume_status"], "rolling_candle_average")
        self.assertIn("evidence_scorecard", candidate["key_signals"])
        self.assertIn("missing_or_planned_modules", candidate["key_signals"]["evidence_scorecard"])
        self.assertIn("evidence_packet", candidate)
        self.assertEqual(candidate["evidence_packet"]["build_version"], "2026.06.11-three-loss-guard")
        self.assertIn("provider_lineage", candidate["evidence_packet"])
        self.assertIn("relative_strength", candidate["key_signals"])

    def test_sideways_data_returns_pass(self) -> None:
        with TempContainer() as container:
            container.scanner.market_data = MockAdapter({"SPY": quote("SPY", 100)}, {"SPY": candles("SPY", 100, 0.001)})
            result = container.scanner.run_market_scan("day_trade", ["SPY"])
        self.assertEqual(result["top_candidates"], [])

    def test_scalp_mode_uses_scalp_watchlist_when_no_tickers_given(self) -> None:
        with TempContainer() as container:
            universe = container.scanner._universe_for_mode("scalp_review", None)

        self.assertIn("NVDA", universe)
        self.assertIn("TSLA", universe)
        self.assertGreater(len(universe), len(container.settings.default_watchlist))

    def test_scalp_mode_can_score_moving_ticker(self) -> None:
        with TempContainer() as container:
            container.scanner.market_data = MockAdapter({"NVDA": quote("NVDA", 106)}, {"NVDA": candles("NVDA", 100, 0.55, volume=300000)})
            result = container.scanner.run_market_scan("scalp_review", ["NVDA"])

        self.assertGreater(len(result["top_candidates"]), 0)
        candidate = result["top_candidates"][0]
        self.assertEqual(candidate["key_signals"]["scan_profile"], "scalp")
        self.assertIn(candidate["direction"], {"long", "short"})
        scorecard = candidate["key_signals"]["evidence_scorecard"]
        self.assertEqual(scorecard["model"], "research_report_v1_preview")
        self.assertIn("modules", scorecard)
        self.assertIn("data_confidence", candidate["evidence_packet"])

    def test_relative_strength_vs_spy_is_available_when_benchmark_exists(self) -> None:
        with TempContainer() as container:
            container.scanner.market_data = MockAdapter(
                {"NVDA": quote("NVDA", 106), "SPY": quote("SPY", 101)},
                {"NVDA": candles("NVDA", 100, 0.55, volume=300000), "SPY": candles("SPY", 100, 0.08, volume=500000)},
            )
            result = container.scanner.run_market_scan("scalp_review", ["NVDA"])

        candidate = result["top_candidates"][0]
        rs = candidate["key_signals"]["relative_strength"]
        self.assertEqual(rs["status"], "available")
        self.assertEqual(rs["benchmark"], "SPY")
        self.assertIn(rs["label"], {"leading_spy", "mixed_vs_spy", "lagging_spy"})
        module_names = [module["name"] for module in candidate["key_signals"]["evidence_scorecard"]["modules"]]
        self.assertIn("relative_strength_vs_spy", module_names)


