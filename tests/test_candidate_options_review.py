from __future__ import annotations

import unittest

from app.mcp_server import _review_candidate_for_options


class FakeEvents:
    def __init__(self):
        self.logged = []

    def log(self, event_type: str, payload: dict) -> dict:
        result = {"logged": True, "event_type": event_type, **payload}
        self.logged.append(result)
        return result


class FakeScanner:
    def __init__(self, item: dict):
        self.item = item

    def run_market_scan(self, mode: str, tickers: list[str], max_candidates: int) -> dict:
        del mode, tickers, max_candidates
        bucket = "top_candidates" if self.item["status"] == "CANDIDATE" else "pass_list"
        other = "pass_list" if bucket == "top_candidates" else "top_candidates"
        return {bucket: [self.item], other: []}


class FakeOptions:
    def __init__(self, result: dict):
        self.result = result
        self.calls = 0

    def validate_chain(self, ticker: str, direction: str, max_contract_price: float | None) -> dict:
        self.last_max_contract_price = max_contract_price
        del ticker, direction
        self.calls += 1
        return self.result


class FakeSetupMemory:
    def compare_snapshot(self, snapshot: dict, limit: int = 100) -> dict:
        del limit
        return {
            "status": "SETUP_MEMORY_READY",
            "memory_signal": "NO_MEMORY_YET",
            "fingerprint": {"ticker": snapshot.get("ticker"), "tags": []},
            "similar_review_summary": {"sample_size": 0},
            "similar_lesson_summary": {"sample_size": 0},
            "review_only": True,
            "can_place_order_from_this_mcp": False,
        }


class FakeContainer:
    def __init__(self, stock_item: dict, options_result: dict):
        self.events = FakeEvents()
        self.scanner = FakeScanner(stock_item)
        self.options = FakeOptions(options_result)
        self.setup_memory = FakeSetupMemory()
        self.settings = type("Settings", (), {"scalp_min_relative_volume": 1.15, "scalp_max_contract_price": 1.0})()


class CandidateOptionsReviewTests(unittest.TestCase):
    def test_candidate_forces_options_validation(self) -> None:
        container = FakeContainer(
            {"ticker": "PG", "status": "CANDIDATE", "score": 72},
            {"status": "NO_TRADE_PLAN", "accepted_contracts": []},
        )

        result = _review_candidate_for_options(container, "PG", "call", "conservative_review_only", None)

        self.assertEqual(container.options.calls, 1)
        self.assertEqual(result["status"], "NO_TRADE_PLAN")
        self.assertEqual(result["options_chain_validation"]["status"], "NO_TRADE_PLAN")
        self.assertFalse(result["can_place_order_from_this_mcp"])

    def test_pass_stock_setup_skips_options_validation(self) -> None:
        container = FakeContainer(
            {"ticker": "PG", "status": "PASS", "score": 50},
            {"status": "OPTIONS_CHAIN_ACCEPTABLE"},
        )

        result = _review_candidate_for_options(container, "PG", "call", "conservative_review_only", None)

        self.assertEqual(container.options.calls, 0)
        self.assertEqual(result["status"], "NO_TRADE_PLAN")
        self.assertIsNone(result["options_chain_validation"])

    def test_acceptable_options_still_remains_review_only(self) -> None:
        container = FakeContainer(
            {"ticker": "PG", "status": "CANDIDATE", "score": 72},
            {"status": "OPTIONS_CHAIN_ACCEPTABLE", "accepted_contracts": [{"contract_symbol": "PGTEST"}]},
        )

        result = _review_candidate_for_options(container, "PG", "call", "conservative_review_only", None)

        self.assertEqual(result["status"], "REVIEW_ONLY_OPTIONS_READY")
        self.assertTrue(result["review_only"])
        self.assertFalse(result["order_allowed"])
        self.assertEqual(result["setup_memory"]["memory_signal"], "NO_MEMORY_YET")

    def test_scalp_candidate_with_low_relative_volume_warns_but_can_advance(self) -> None:
        container = FakeContainer(
            {"ticker": "SMCI", "status": "CANDIDATE", "score": 76, "key_signals": {"relative_volume": 0.28}},
            {"status": "OPTIONS_CHAIN_ACCEPTABLE", "accepted_contracts": [{"contract_symbol": "SMCITEST"}]},
        )

        result = _review_candidate_for_options(container, "SMCI", "put", "scalp_review", None)

        self.assertEqual(container.options.calls, 1)
        self.assertEqual(result["status"], "REVIEW_ONLY_OPTIONS_READY")
        self.assertIn("relative volume", " ".join(result["warnings"]).lower())
        self.assertFalse(result["order_allowed"])

    def test_scalp_candidate_with_supportive_relative_volume_can_advance(self) -> None:
        container = FakeContainer(
            {"ticker": "SMCI", "status": "CANDIDATE", "score": 76, "key_signals": {"relative_volume": 1.5}},
            {"status": "OPTIONS_CHAIN_ACCEPTABLE", "accepted_contracts": [{"contract_symbol": "SMCITEST"}]},
        )

        result = _review_candidate_for_options(container, "SMCI", "put", "scalp_review", None)

        self.assertEqual(container.options.calls, 1)
        self.assertEqual(result["status"], "REVIEW_ONLY_OPTIONS_READY")

    def test_small_account_scalp_review_blocks_1dte_or_large_max_loss(self) -> None:
        container = FakeContainer(
            {"ticker": "AAPL", "status": "CANDIDATE", "score": 94, "direction": "short", "key_signals": {"relative_volume": 4.0, "above_vwap": False, "below_vwap": True}},
            {
                "status": "OPTIONS_CHAIN_ACCEPTABLE",
                "accepted_contracts": [
                    {
                        "contract_symbol": "AAPLTEST",
                        "days_to_expiration": 1,
                        "max_loss_dollars": 125,
                        "spread_pct": 0.05,
                    }
                ],
            },
        )

        result = _review_candidate_for_options(container, "AAPL", "put", "scalp_review", None)

        self.assertEqual(result["status"], "NO_TRADE_PLAN")
        self.assertEqual(result["small_account_review"]["status"], "NO_TRADE_PLAN")
        self.assertEqual(result["small_account_review"]["priority_score"], 0.0)
        joined = " ".join(result["warnings"]).lower()
        self.assertIn("1dte", joined)
        self.assertIn("max loss", joined)

    def test_exceptional_1dte_can_remain_review_only(self) -> None:
        container = FakeContainer(
            {"ticker": "QQQ", "status": "CANDIDATE", "score": 94, "direction": "short", "key_signals": {"relative_volume": 2.0, "above_vwap": False, "below_vwap": True}},
            {
                "status": "OPTIONS_CHAIN_ACCEPTABLE",
                "accepted_contracts": [
                    {
                        "contract_symbol": "QQQTEST",
                        "days_to_expiration": 1,
                        "max_loss_dollars": 18,
                        "spread_pct": 0.05,
                        "bid": 0.17,
                        "ask": 0.18,
                    }
                ],
            },
        )

        result = _review_candidate_for_options(container, "QQQ", "put", "scalp_review", None)

        self.assertEqual(result["status"], "REVIEW_ONLY_OPTIONS_READY")
        self.assertEqual(result["small_account_review"]["status"], "SMALL_ACCOUNT_SCALP_ACCEPTABLE")

    def test_small_account_scalp_review_caps_priority_when_warnings_exist(self) -> None:
        container = FakeContainer(
            {"ticker": "SOFI", "status": "CANDIDATE", "score": 94, "direction": "short", "key_signals": {"relative_volume": 2.4, "above_vwap": False, "below_vwap": True}},
            {
                "status": "OPTIONS_CHAIN_ACCEPTABLE",
                "accepted_contracts": [
                    {
                        "contract_symbol": "SOFITEST",
                        "days_to_expiration": 3,
                        "max_loss_dollars": 8,
                        "spread_pct": 0.12,
                        "bid": 0.07,
                        "ask": 0.08,
                        "volume": 3500,
                        "open_interest": 8000,
                    }
                ],
            },
        )

        result = _review_candidate_for_options(container, "SOFI", "put", "scalp_review", None)

        self.assertEqual(result["status"], "REVIEW_ONLY_OPTIONS_READY")
        self.assertEqual(result["small_account_review"]["priority_score"], 86.0)
        self.assertEqual(result["small_account_review"]["friction_adjusted_score"], 86.0)
        self.assertEqual(result["small_account_review"]["friction_band"], "LOW_FRICTION")
        self.assertIn("spread", " ".join(result["warnings"]).lower())

    def test_high_friction_contract_blocks_small_account_review(self) -> None:
        container = FakeContainer(
            {"ticker": "SMCI", "status": "CANDIDATE", "score": 94, "direction": "short", "key_signals": {"relative_volume": 2.4, "above_vwap": False, "below_vwap": True}},
            {
                "status": "OPTIONS_CHAIN_ACCEPTABLE",
                "accepted_contracts": [
                    {
                        "contract_symbol": "SMCITHIN",
                        "days_to_expiration": 3,
                        "max_loss_dollars": 90,
                        "spread_pct": 0.14,
                        "bid": 0.50,
                        "ask": 0.58,
                        "volume": 12,
                        "open_interest": 40,
                    }
                ],
            },
        )

        result = _review_candidate_for_options(container, "SMCI", "put", "scalp_review", None)

        self.assertEqual(result["status"], "NO_TRADE_PLAN")
        self.assertEqual(result["small_account_review"]["status"], "NO_TRADE_PLAN")
        self.assertEqual(result["small_account_review"]["friction_band"], "BLOCKED_BY_FRICTION")
        self.assertIn("friction-adjusted", " ".join(result["warnings"]).lower())

    def test_scalp_review_defaults_to_small_account_contract_cap(self) -> None:
        container = FakeContainer(
            {"ticker": "SOFI", "status": "CANDIDATE", "score": 94, "direction": "short", "key_signals": {"relative_volume": 2.4, "above_vwap": False, "below_vwap": True}},
            {"status": "OPTIONS_CHAIN_ACCEPTABLE", "accepted_contracts": [{"contract_symbol": "SOFITEST", "days_to_expiration": 3, "max_loss_dollars": 8, "spread_pct": 0.04}]},
        )

        result = _review_candidate_for_options(container, "SOFI", "put", "scalp_review", None)

        self.assertEqual(container.options.last_max_contract_price, 1.0)
        self.assertEqual(result["max_contract_price_used"], 1.0)

    def test_failed_options_chain_has_zero_small_account_priority(self) -> None:
        container = FakeContainer(
            {"ticker": "AAPL", "status": "CANDIDATE", "score": 94, "direction": "short", "key_signals": {"relative_volume": 4.0, "above_vwap": False, "below_vwap": True}},
            {"status": "NO_TRADE_PLAN", "accepted_contracts": []},
        )

        result = _review_candidate_for_options(container, "AAPL", "put", "scalp_review", None)

        self.assertEqual(result["status"], "NO_TRADE_PLAN")
        self.assertEqual(result["small_account_review"]["priority_score"], 0.0)
        self.assertIsNone(result["small_account_review"]["selected_contract"])
