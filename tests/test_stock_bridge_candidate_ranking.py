from __future__ import annotations

import asyncio
import unittest
from typing import Any
from unittest.mock import patch

from tools.stock_bridge_loop import BridgeConfig, manage_positions, rank_long_candidates, select_long_candidate


def run(coro):
    return asyncio.run(coro)


def config(**overrides: Any) -> BridgeConfig:
    values = {
        "broker": "alpaca",
        "base_url": "https://living-screener-mcp.onrender.com",
        "mcp_url": "https://agent.robinhood.com/mcp/trading",
        "account_number": "",
        "alpaca_base_url": "https://paper-api.alpaca.markets",
        "alpaca_data_url": "https://data.alpaca.markets",
        "alpaca_api_key_id": "key",
        "alpaca_api_secret_key": "secret",
        "live": False,
        "interval_seconds": 60,
        "once": True,
        "min_score": 76.0,
        "min_relative_volume": 0.45,
        "max_spread_bps": 35.0,
        "max_order_notional": 15.0,
        "min_order_notional": 1.0,
        "max_open_positions": 5,
        "max_trades_per_day": 10,
        "max_daily_loss": 20.0,
        "stop_loss_pct": 0.0035,
        "take_profit_pct": 0.0045,
        "allowed_broker_alert_types": (),
        "account_value": 100.0,
        "scan_max_candidates": 60,
        "scan_review_top_n": 20,
        "auth_timeout_seconds": 300,
        "max_consecutive_errors": 2,
        "error_cooldown_seconds": 300,
        "market_hours": "auto",
        "enable_crypto_execution": False,
        "allow_market_options": False,
        "allow_market_crypto": False,
        "max_option_contract_cost": 15.0,
        "max_option_account_risk": 20.0,
    }
    values.update(overrides)
    return BridgeConfig(**values)


def candidate(
    ticker: str,
    stock_score: float,
    relative_volume: float = 1.2,
    evidence_score: float = 80.0,
    confidence_score: float = 85.0,
    confidence_status: str = "HIGH",
    relative_strength_label: str = "leading_spy",
    data_flags: list[str] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    row = {
        "ticker": ticker,
        "stock_score": stock_score,
        "relative_volume": relative_volume,
        "stock_direction": "long",
        "stock_setup_quality": "VALID_CANDIDATE",
        "vwap_state": "above",
        "key_signals": {
            "evidence_scorecard": {"preview_final_score": evidence_score},
            "relative_strength": {
                "label": relative_strength_label,
                "excess_trend_pct": 0.012 if "leading" in relative_strength_label else -0.004,
                "excess_recent_trend_pct": 0.004,
            },
        },
        "evidence_packet": {
            "data_confidence": {"score": confidence_score, "status": confidence_status},
            "data_flags": data_flags or [],
        },
    }
    row.update(overrides)
    return row


def quotes(*symbols: str) -> dict[str, dict[str, str]]:
    return {
        symbol: {"bid_price": "99.90", "ask_price": "100.00", "last_trade_price": "99.95"}
        for symbol in symbols
    }


def tradability(*symbols: str) -> dict[str, dict[str, Any]]:
    return {symbol: {"tradeable": True, "state": "active"} for symbol in symbols}


class StockBridgeCandidateRankingTests(unittest.TestCase):
    def test_evidence_backed_candidate_can_outrank_higher_raw_score(self) -> None:
        weak_high_score = candidate(
            "WEAK",
            88,
            evidence_score=15,
            confidence_score=60,
            confidence_status="MEDIUM",
            relative_strength_label="lagging_spy",
            data_flags=["quote_derived_from_candles"],
        )
        strong_lower_score = candidate(
            "EDGE",
            84,
            evidence_score=92,
            confidence_score=92,
            confidence_status="HIGH",
            relative_strength_label="leading_spy",
            data_flags=["catalyst_context_missing", "sector_relative_strength_missing", "l2_order_flow_missing"],
        )

        ranked = rank_long_candidates(
            [weak_high_score, strong_lower_score],
            quotes("WEAK", "EDGE"),
            tradability("WEAK", "EDGE"),
            set(),
            config(),
        )

        self.assertEqual(ranked[0]["symbol"], "EDGE")
        self.assertTrue(ranked[0]["rank_score"] > ranked[1]["rank_score"])

    def test_stale_data_is_rejected_before_selection(self) -> None:
        stale = candidate("STALE", 99, data_flags=["quote_stale"], confidence_score=80, confidence_status="HIGH")
        clean = candidate("CLEAN", 78, evidence_score=70, confidence_score=80, confidence_status="HIGH")

        ranked = rank_long_candidates(
            [stale, clean],
            quotes("STALE", "CLEAN"),
            tradability("STALE", "CLEAN"),
            set(),
            config(),
        )

        stale_diag = next(item for item in ranked if item["symbol"] == "STALE")
        self.assertFalse(stale_diag["passed"])
        self.assertIn("stale_market_data", stale_diag["rejection_reasons"])
        self.assertEqual(ranked[0]["symbol"], "CLEAN")

    def test_selector_logs_ranking_summary_and_returns_bridge_profile(self) -> None:
        clean = candidate("CLEAN", 80, evidence_score=88, confidence_score=91)

        with patch("tools.stock_bridge_loop.append_log") as append_log:
            selected = select_long_candidate(
                [clean],
                quotes("CLEAN"),
                tradability("CLEAN"),
                set(),
                config(),
            )

        self.assertIsNotNone(selected)
        self.assertEqual(selected["scan"]["ticker"], "CLEAN")
        self.assertIn("bridge_rank_score", selected)
        self.assertIn("bridge_evidence_profile", selected)
        append_log.assert_called_once()
        self.assertEqual(append_log.call_args.args[0]["event"], "candidate_ranking_summary")

    def test_existing_hard_gates_still_block_invalid_candidate(self) -> None:
        bad = candidate("BAD", 95, relative_volume=2.0, vwap_state="below")
        ranked = rank_long_candidates(
            [bad],
            quotes("BAD"),
            tradability("BAD"),
            set(),
            config(),
        )

        self.assertFalse(ranked[0]["passed"])
        self.assertIn("not_above_vwap", ranked[0]["rejection_reasons"])

    def test_exit_place_failure_is_logged_without_raising(self) -> None:
        class FailingExitBroker:
            async def positions(self) -> list[dict[str, str]]:
                return [{"symbol": "CELH", "shares_available_for_sells": "8", "quantity": "8.5", "average_buy_price": "40"}]

            async def quotes(self, symbols: list[str]) -> dict[str, dict[str, str]]:
                return {"CELH": {"last_trade_price": "41", "bid_price": "40.99", "ask_price": "41.01"}}

            async def review_order(self, args: dict[str, Any]) -> dict[str, Any]:
                return {"order_checks": {}, "normalized_intent": args}

            async def place_order(self, args: dict[str, Any]) -> dict[str, Any]:
                raise RuntimeError("broker refused exit")

        with patch("tools.stock_bridge_loop.append_log") as append_log:
            run(manage_positions(FailingExitBroker(), config(live=True, take_profit_pct=0.01), {}))  # type: ignore[arg-type]

        events = [call.args[0]["event"] for call in append_log.call_args_list]
        self.assertIn("exit_review", events)
        self.assertIn("exit_place_failed", events)


if __name__ == "__main__":
    unittest.main()
