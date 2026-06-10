from __future__ import annotations

import unittest
from unittest.mock import patch

from app.mcp_server import _run_go_live_rehearsal
from tests.helpers import TempContainer


class GoLiveRehearsalTests(unittest.TestCase):
    def test_rehearsal_is_ready_without_market_check(self) -> None:
        with TempContainer() as container:
            result = _run_go_live_rehearsal(container, ["SOFI", "SMCI"], 50, 25, False)

        self.assertEqual(result["event_type"], "go_live_rehearsal")
        self.assertEqual(result["status"], "GO_LIVE_REHEARSAL_READY")
        self.assertFalse(result["include_market_check"])
        self.assertIn("Root operator brief", [item["label"] for item in result["required_live_urls"]])
        self.assertIn("Day monitor", [item["label"] for item in result["tomorrow_open_tabs"]])
        self.assertFalse(result["can_place_order_from_this_mcp"])

    def test_rehearsal_uses_configured_universe_when_tickers_omitted(self) -> None:
        with TempContainer() as container:
            result = _run_go_live_rehearsal(container, None, 50, 25, False)

        self.assertEqual(result["status"], "GO_LIVE_REHEARSAL_READY")
        self.assertIn("SPY", result["universe"])
        self.assertIn("Go-live rehearsal", [item["label"] for item in result["required_live_urls"]])

    def test_rehearsal_blocks_when_session_risk_blocks(self) -> None:
        with TempContainer() as container:
            for index in range(2):
                container.events.log(
                    "manual_option_paper_entry",
                    {
                        "status": "PAPER_OPTION_ENTRY_OPEN",
                        "ticker": "SOFI",
                        "contract_symbol": f"SOFI260612P0001500{index}",
                        "entry_debit_dollars": 8.0,
                    },
                )
            result = _run_go_live_rehearsal(container, ["SOFI"], 50, 25, False)

        self.assertEqual(result["status"], "GO_LIVE_REHEARSAL_BLOCKED")
        self.assertTrue(result["blocking_reasons"])
        self.assertEqual(result["operator_brief"]["session_risk_status"], "SESSION_RISK_BLOCKED")

    def test_rehearsal_can_include_market_readiness_caution(self) -> None:
        fake_readiness = {
            "status": "MARKET_DATA_READY_NO_CANDIDATES",
            "mode": "scalp_review",
            "candidate_count": 0,
            "valid_row_count": 5,
            "quote_problem_count": 0,
            "review_only": True,
            "can_place_order_from_this_mcp": False,
        }
        with TempContainer() as container, patch("app.mcp_server._market_readiness_check", return_value=fake_readiness):
            result = _run_go_live_rehearsal(container, ["SOFI"], 50, 25, True)

        self.assertEqual(result["status"], "GO_LIVE_REHEARSAL_CAUTION")
        self.assertTrue(result["include_market_check"])
        self.assertEqual(result["market_readiness"]["status"], "MARKET_DATA_READY_NO_CANDIDATES")
        self.assertTrue(result["warnings"])


if __name__ == "__main__":
    unittest.main()
