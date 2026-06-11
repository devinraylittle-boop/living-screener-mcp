from __future__ import annotations

import unittest

from app.services.options_service import OptionsService
from tests.helpers import TempContainer


class OptionsServiceTests(unittest.TestCase):
    def test_contract_quality_accepts_liquid_contract(self) -> None:
        with TempContainer() as container:
            service = OptionsService(container.settings, container.events)
            contract = {
                "bid": 1.0,
                "ask": 1.1,
                "volume": 50,
                "open_interest": 500,
                "days_to_expiration": 7,
                "max_loss_dollars": 110,
            }

            result = service._score_contract(contract, None)

        self.assertEqual(result["quality_status"], "ACCEPTABLE")
        self.assertEqual(result["reasons"], [])

    def test_contract_quality_rejects_missing_liquidity_and_wide_spread(self) -> None:
        with TempContainer() as container:
            service = OptionsService(container.settings, container.events)
            contract = {
                "bid": 0.05,
                "ask": 0.25,
                "volume": 0,
                "open_interest": 0,
                "days_to_expiration": 0,
                "max_loss_dollars": 25,
            }

            result = service._score_contract(contract, None)

        self.assertEqual(result["quality_status"], "REJECTED")
        self.assertIn("Bid/ask spread too wide.", result["reasons"])
        self.assertIn("Contract volume below floor.", result["reasons"])
        self.assertIn("Open interest below floor.", result["reasons"])
        self.assertIn("Expiration is too close.", result["reasons"])

    def test_no_trade_result_is_review_only(self) -> None:
        with TempContainer() as container:
            service = OptionsService(container.settings, container.events)
            result = service._log_no_trade("PG", ["missing"], "calls")

        self.assertEqual(result["status"], "NO_TRADE_PLAN")
        self.assertTrue(result["review_only"])
        self.assertFalse(result["can_place_order_from_this_mcp"])

    def test_broker_snapshot_validation_accepts_clean_small_contract(self) -> None:
        with TempContainer() as container:
            service = OptionsService(container.settings, container.events)
            result = service.validate_broker_snapshot(
                {
                    "ticker": "SOFI",
                    "contract_symbol": "SOFITEST",
                    "direction": "put",
                    "bid": 0.20,
                    "ask": 0.22,
                    "volume": 250,
                    "open_interest": 1000,
                    "dte": 3,
                    "strike": 15,
                },
                max_contract_price=1.0,
            )

        self.assertEqual(result["status"], "OPTIONS_CHAIN_ACCEPTABLE")
        self.assertEqual(result["chain_provider"], "broker_snapshot_manual")
        self.assertEqual(result["option_snapshot_v2"]["schema_version"], "OptionSnapshotV2")
        self.assertEqual(result["option_snapshot_v2"]["contract_symbol"], "SOFITEST")
        self.assertEqual(result["option_snapshot_v2"]["quote_time_source"], "captured_at_validation")
        self.assertEqual(result["liquidity_gate_result"]["status"], "LIQUIDITY_GATE_PASS")
        self.assertEqual(result["mismatch_codes"], [])
        self.assertFalse(result["can_place_order_from_this_mcp"])

    def test_broker_snapshot_validation_rejects_wide_or_expensive_contract(self) -> None:
        with TempContainer() as container:
            service = OptionsService(container.settings, container.events)
            result = service.validate_broker_snapshot(
                {
                    "ticker": "LULU",
                    "contract_symbol": "LULUTEST",
                    "direction": "put",
                    "bid": 1.00,
                    "ask": 2.00,
                    "volume": 250,
                    "open_interest": 1000,
                    "dte": 3,
                    "strike": 300,
                },
                max_contract_price=1.0,
            )

        self.assertEqual(result["status"], "NO_TRADE_PLAN")
        reasons = result["rejected_sample"][0]["reasons"]
        self.assertIn("Bid/ask spread too wide.", reasons)
        self.assertIn("Ask exceeds configured max contract price.", reasons)
        self.assertIn("Would pass spread gate", result["rejected_sample"][0]["closest_to_pass_reason"])
        self.assertTrue(result["quality_gate"]["volume"])
        self.assertTrue(result["quality_gate"]["open_interest"])
        self.assertFalse(result["quality_gate"]["bid_ask_spread"])
        self.assertFalse(result["quality_gate"]["max_loss"])

    def test_broker_snapshot_requires_identifying_fields(self) -> None:
        with TempContainer() as container:
            service = OptionsService(container.settings, container.events)
            result = service.validate_broker_snapshot(
                {
                    "direction": "put",
                    "bid": 0.20,
                    "ask": 0.22,
                    "volume": 250,
                    "open_interest": 1000,
                    "dte": 3,
                    "strike": 15,
                },
                max_contract_price=1.0,
            )

        self.assertEqual(result["status"], "NO_TRADE_PLAN")
        reasons = result["rejected_sample"][0]["reasons"]
        self.assertIn("Ticker missing.", reasons)
        self.assertIn("Contract symbol missing.", reasons)

    def test_broker_snapshot_blocks_contract_mismatch_and_adjusted_contract(self) -> None:
        with TempContainer() as container:
            service = OptionsService(container.settings, container.events)
            result = service.validate_broker_snapshot(
                {
                    "ticker": "SOFI",
                    "contract_symbol": "SOFI_WRONG",
                    "expected_contract_symbol": "SOFI_EXPECTED",
                    "direction": "put",
                    "bid": 0.20,
                    "ask": 0.22,
                    "volume": 250,
                    "open_interest": 1000,
                    "dte": 3,
                    "strike": 15,
                    "is_adjusted": True,
                },
                max_contract_price=1.0,
            )

        self.assertEqual(result["status"], "NO_TRADE_PLAN")
        self.assertIn("BROKER_CONTRACT_MISMATCH", result["mismatch_codes"])
        self.assertIn("ADJUSTED_CONTRACT", result["mismatch_codes"])
        self.assertEqual(result["liquidity_gate_result"]["status"], "LIQUIDITY_GATE_BLOCK")
        self.assertFalse(result["quality_gate"]["contract_identity"])
