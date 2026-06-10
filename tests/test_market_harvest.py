from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.mcp_server import _get_market_session_playbook, _get_ops_command_center, _market_readiness_check, _run_latest_harvest_followup, _run_live_review_cycle, _run_morning_readiness_autopilot, _run_review_harvest


class FakeEvents:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def log(self, event_type: str, payload: dict) -> dict:
        row = {
            "id": len(self.rows) + 1,
            "logged": True,
            "event_type": event_type,
            "timestamp": "2026-06-09T20:00:00+00:00",
            **payload,
        }
        self.rows.append({"id": row["id"], "event_type": event_type, "timestamp": row["timestamp"], "payload": payload})
        return row

    def recent(self, event_type: str | None = None, limit: int = 100) -> list[dict]:
        rows = [row for row in self.rows if event_type is None or row["event_type"] == event_type]
        return list(reversed(rows))[:limit]

    def count(self, event_type: str | None = None) -> int:
        return len([row for row in self.rows if event_type is None or row["event_type"] == event_type])


class FakeScanner:
    def run_market_scan(self, mode: str, tickers: list[str] | None = None, max_candidates: int = 25) -> dict:
        del max_candidates
        ticker = (tickers or ["SOFI"])[0]
        candidate = {
            "ticker": ticker,
            "status": "CANDIDATE",
            "score": 88,
            "confidence": "medium",
            "direction": "short",
            "setup_type": mode,
            "quote_summary": {"price": 16.25, "timestamp": "2026-06-09T20:00:00+00:00", "provider": "test"},
            "quality_gates": {"stock_setup_quality": "VALID_CANDIDATE"},
            "key_signals": {
                "relative_volume": 2.4,
                "above_vwap": False,
                "below_vwap": True,
                "relative_strength": {"label": "leading_spy"},
            },
            "data_status": "valid",
            "review_only": True,
            "order_allowed": False,
        }
        return {
            "mode": mode,
            "data_provider": "test",
            "data_status": "available",
            "market_regime": {"regime": "review-data-available"},
            "top_candidates": [candidate],
            "pass_list": [],
        }


class FakeOptions:
    def validate_chain(self, ticker: str, direction: str, max_contract_price: float | None = None) -> dict:
        del ticker, direction, max_contract_price
        return {
            "status": "OPTIONS_CHAIN_ACCEPTABLE",
            "accepted_contracts": [
                {
                    "contract_symbol": "SOFI260612P00015000",
                    "expiration": "2026-06-12",
                    "strike": 15,
                    "days_to_expiration": 3,
                    "bid": 0.07,
                    "ask": 0.08,
                    "spread_pct": 0.04,
                    "volume": 4000,
                    "open_interest": 8000,
                    "max_loss_dollars": 8,
                }
            ],
        }


class FakeSetupMemory:
    def compare_snapshot(self, snapshot: dict, limit: int = 100) -> dict:
        del snapshot, limit
        return {"status": "SETUP_MEMORY_READY", "memory_signal": "NO_MEMORY_YET"}


class FakeReviewOutcomes:
    def check_review_outcome(self, review: dict, horizons: dict | None = None) -> dict:
        del horizons
        return {
            "ticker": review["ticker"],
            "verdict": "HELPED",
            "current_return_pct": 0.004,
            "max_favorable_excursion": 0.006,
            "max_adverse_excursion": -0.001,
            "review_only": True,
            "can_place_order_from_this_mcp": False,
        }

    def summarize_review_outcomes(self, outcomes: list[dict]) -> dict:
        return {
            "sample_size": len(outcomes),
            "win_rate": 1.0,
            "average_return_pct": 0.004,
            "review_only": True,
            "can_place_order_from_this_mcp": False,
        }


class FakeLearning:
    def classify_review_outcome(self, snapshot: dict, outcome: dict, help_threshold: float = 0.003, missed_move_threshold: float = 0.006) -> dict:
        del snapshot, outcome, help_threshold, missed_move_threshold
        return {
            "ticker": "SOFI",
            "classification": "GOOD_SIGNAL",
            "lesson_tags": ["wide_spread"],
            "review_only": True,
            "can_place_order_from_this_mcp": False,
        }

    def summarize_learning(self, classifications: list[dict], limit: int = 100) -> dict:
        del limit
        return {
            "sample_size": len(classifications),
            "classification_counts": {"GOOD_SIGNAL": len(classifications)},
            "review_only": True,
            "can_place_order_from_this_mcp": False,
        }


class MarketHarvestTests(unittest.TestCase):
    def container(self) -> SimpleNamespace:
        events = FakeEvents()
        return SimpleNamespace(
            scanner=FakeScanner(),
            options=FakeOptions(),
            events=events,
            setup_memory=FakeSetupMemory(),
            review_outcomes=FakeReviewOutcomes(),
            learning=FakeLearning(),
            settings=SimpleNamespace(
                scalp_min_relative_volume=1.15,
                scalp_max_contract_price=1.0,
                scalp_watchlist=("SOFI", "SMCI"),
                default_tickers=("SOFI", "SMCI"),
                max_trade_risk_pct=0.10,
                warn_daily_drawdown_pct=0.10,
                soft_stop_daily_drawdown_pct=0.20,
                hard_lockout_daily_drawdown_pct=0.30,
            ),
        )

    def test_market_readiness_reports_review_ready_without_execution(self) -> None:
        result = _market_readiness_check(self.container(), ["SOFI"], 5)

        self.assertEqual(result["event_type"], "market_readiness")
        self.assertEqual(result["status"], "MARKET_REVIEW_READY")
        self.assertEqual(result["candidate_count"], 1)
        self.assertFalse(result["can_place_order_from_this_mcp"])

    def test_review_harvest_ranks_only_small_account_acceptable_reviews(self) -> None:
        result = _run_review_harvest(self.container(), ["SOFI"], "scalp_review", 5, 3, None)

        self.assertEqual(result["event_type"], "review_harvest")
        self.assertEqual(result["status"], "REVIEW_HARVEST_READY")
        self.assertEqual(result["eligible_count"], 1)
        self.assertEqual(result["ranked_candidates"][0]["ticker"], "SOFI")
        self.assertEqual(result["ranked_candidates"][0]["contract"], "SOFI260612P00015000")
        self.assertEqual(result["followup_checks"][0]["check_after_minutes"], [15, 30, 60])
        self.assertFalse(result["can_place_order_from_this_mcp"])

    def test_session_playbook_is_review_only_and_actionable(self) -> None:
        result = _get_market_session_playbook(self.container(), ["SOFI", "SMCI"], 50)

        self.assertEqual(result["event_type"], "session_playbook")
        self.assertEqual(result["status"], "SESSION_PLAYBOOK_READY")
        self.assertIn("/ops/review-harvest", result["session_blocks"][2]["actions"][0])
        self.assertIn("Build and safety confirmed.", result["manual_trade_gate"])
        self.assertIn("Session risk guard is not SESSION_RISK_BLOCKED.", result["manual_trade_gate"])
        self.assertFalse(result["can_place_order_from_this_mcp"])

    def test_latest_harvest_followup_closes_learning_loop(self) -> None:
        container = self.container()
        _run_review_harvest(container, ["SOFI"], "scalp_review", 5, 3, None)

        result = _run_latest_harvest_followup(container, 5, True)

        self.assertEqual(result["event_type"], "harvest_followup")
        self.assertEqual(result["status"], "HARVEST_FOLLOWUP_COMPLETE")
        self.assertEqual(result["checks_completed"], 1)
        self.assertEqual(result["outcomes"][0]["verdict"], "HELPED")
        self.assertEqual(result["classifications"][0]["classification"], "GOOD_SIGNAL")
        self.assertFalse(result["can_place_order_from_this_mcp"])

    def test_latest_harvest_followup_fails_safely_without_harvest(self) -> None:
        result = _run_latest_harvest_followup(self.container(), 5, True)

        self.assertEqual(result["status"], "NO_HARVEST_TO_FOLLOW_UP")
        self.assertEqual(result["outcomes"], [])
        self.assertFalse(result["can_place_order_from_this_mcp"])

    def test_command_center_moves_from_readiness_to_followup(self) -> None:
        container = self.container()

        first = _get_ops_command_center(container, ["SOFI"], 50)
        self.assertEqual(first["status"], "NEEDS_MARKET_READINESS")
        self.assertEqual(first["next_action"]["endpoint"], "/ops/market-readiness")

        _market_readiness_check(container, ["SOFI"], 5)
        second = _get_ops_command_center(container, ["SOFI"], 50)
        self.assertEqual(second["status"], "READY_FOR_HARVEST")
        self.assertEqual(second["next_action"]["endpoint"], "/ops/review-harvest")

        _run_review_harvest(container, ["SOFI"], "scalp_review", 5, 3, None)
        third = _get_ops_command_center(container, ["SOFI"], 50)
        self.assertEqual(third["status"], "HARVEST_READY_NEEDS_FOLLOWUP")
        self.assertEqual(third["next_action"]["endpoint"], "/ops/harvest-followup")
        self.assertEqual(third["latest"]["session_risk_guard"]["status"], "SESSION_RISK_CLEAR")
        self.assertFalse(third["can_place_order_from_this_mcp"])

    def test_morning_autopilot_summarizes_readiness_without_execution(self) -> None:
        result = _run_morning_readiness_autopilot(self.container(), ["SOFI"], 50, 5)

        self.assertEqual(result["event_type"], "morning_readiness_autopilot")
        self.assertIn(result["status"], {"AUTOPILOT_READY_FOR_HARVEST", "AUTOPILOT_KEEP_SCANNING", "AUTOPILOT_DATA_BLOCKED", "AUTOPILOT_STANDBY", "AUTOPILOT_SESSION_RISK_BLOCKED"})
        self.assertIn("readiness", result)
        self.assertIn("session_risk_guard", result)
        self.assertIn("paper_ledger", result)
        self.assertIn("review_harvest", result["action_links"])
        self.assertFalse(result["can_place_order_from_this_mcp"])
        self.assertFalse(result["can_cancel_order_from_this_mcp"])

    def test_live_review_cycle_runs_harvest_when_data_is_usable(self) -> None:
        result = _run_live_review_cycle(self.container(), ["SOFI"], 50, 5, 3, None, False)

        self.assertEqual(result["event_type"], "live_review_cycle")
        self.assertIn(result["status"], {"LIVE_CYCLE_CANDIDATES_READY", "NO_TRADE_PLAN", "LIVE_CYCLE_DATA_BLOCKED", "LIVE_CYCLE_STANDBY", "LIVE_CYCLE_SESSION_RISK_BLOCKED"})
        self.assertIn("readiness", result)
        self.assertIn("session_risk_guard", result)
        self.assertIn("paper_ledger", result)
        self.assertIn("manual_preflight", result["action_links"])
        self.assertFalse(result["can_place_order_from_this_mcp"])
        self.assertFalse(result["can_cancel_order_from_this_mcp"])

    def test_live_review_cycle_blocks_manual_preflight_when_session_risk_is_full(self) -> None:
        container = self.container()
        for _ in range(2):
            container.events.log(
                "manual_option_paper_entry",
                {
                    "status": "PAPER_OPTION_ENTRY_OPEN",
                    "ticker": "SOFI",
                    "contract_symbol": "SOFI260612P00015000",
                    "entry_debit_dollars": 8.0,
                },
            )

        result = _run_live_review_cycle(container, ["SOFI"], 50, 5, 3, None, False)

        self.assertEqual(result["status"], "LIVE_CYCLE_SESSION_RISK_BLOCKED")
        self.assertEqual(result["session_risk_guard"]["status"], "SESSION_RISK_BLOCKED")
        self.assertFalse(result["manual_preflight_required"])
        self.assertIn("Session risk guard is not SESSION_RISK_BLOCKED.", result["manual_trade_gate"])


if __name__ == "__main__":
    unittest.main()
