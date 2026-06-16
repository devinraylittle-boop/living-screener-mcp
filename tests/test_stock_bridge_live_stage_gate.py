from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tools.stock_bridge_loop import enforce_live_config_caps, enforce_live_readiness_gate, parse_args


class StockBridgeLiveStageGateTests(unittest.TestCase):
    def test_stage_three_live_is_the_only_currently_allowed_live_stage(self) -> None:
        with patch.dict(os.environ, {"AUTONOMY_STAGE": "stage_3_human_approved_live_trades"}, clear=False):
            enforce_live_readiness_gate(live=True)

    def test_stage_five_live_is_refused_even_with_operator_authorization(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AUTONOMY_STAGE": "stage_5_full_autonomous_with_strict_caps",
                "STOCK_BRIDGE_LIVE_AUTH": "ENABLE_AGENTIC_STOCK_BRIDGE",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(SystemExit, "Full or limited autonomous live trading remains blocked"):
                enforce_live_readiness_gate(live=True)

    def test_stage_five_alpaca_live_cash_route_requires_alpaca_auth(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AUTONOMY_STAGE": "stage_5_full_autonomous_with_strict_caps",
                "ALPACA_LIVE_CASH_AUTONOMY_AUTH": "",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(SystemExit, "Alpaca live-cash Stage 5 is wired"):
                enforce_live_readiness_gate(
                    live=True,
                    broker="alpaca",
                    alpaca_base_url="https://api.alpaca.markets",
                )

    def test_stage_four_live_is_refused_until_gates_are_satisfied(self) -> None:
        with patch.dict(os.environ, {"AUTONOMY_STAGE": "stage_4_limited_autonomous_live_trades"}, clear=False):
            with self.assertRaisesRegex(SystemExit, "requested stage_4_limited_autonomous_live_trades"):
                enforce_live_readiness_gate(live=True)

    def test_paper_or_dry_run_can_use_requested_stage_without_live_orders(self) -> None:
        with patch.dict(os.environ, {"AUTONOMY_STAGE": "stage_2_paper_trading_automation"}, clear=False):
            enforce_live_readiness_gate(live=False)

    def test_alpaca_paper_submission_is_allowed_in_stage_two(self) -> None:
        with patch.dict(os.environ, {"AUTONOMY_STAGE": "stage_2_paper_trading_automation"}, clear=False):
            enforce_live_readiness_gate(
                live=True,
                broker="alpaca",
                alpaca_base_url="https://paper-api.alpaca.markets/v2",
            )

    def test_alpaca_live_endpoint_is_not_allowed_in_stage_two(self) -> None:
        with patch.dict(os.environ, {"AUTONOMY_STAGE": "stage_2_paper_trading_automation"}, clear=False):
            with self.assertRaisesRegex(SystemExit, "requested stage_2_paper_trading_automation"):
                enforce_live_readiness_gate(
                    live=True,
                    broker="alpaca",
                    alpaca_base_url="https://api.alpaca.markets",
                )

    def test_alpaca_live_endpoint_is_not_allowed_in_stage_three_scope(self) -> None:
        with patch.dict(os.environ, {"AUTONOMY_STAGE": "stage_3_human_approved_live_trades"}, clear=False):
            with self.assertRaisesRegex(SystemExit, "only allowed under Stage 5"):
                enforce_live_readiness_gate(
                    live=True,
                    broker="alpaca",
                    alpaca_base_url="https://api.alpaca.markets",
                )

    def test_parse_args_allows_alpaca_paper_submit_without_real_money_auth(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AUTONOMY_STAGE": "stage_2_paper_trading_automation",
                "ALPACA_BASE_URL": "https://paper-api.alpaca.markets/v2",
                "STOCK_BRIDGE_LIVE_AUTH": "",
            },
            clear=False,
        ):
            config = parse_args(["--broker", "alpaca", "--live", "--once"])

        self.assertTrue(config.live)
        self.assertEqual(config.broker, "alpaca")

    def test_parse_args_allows_stage_five_alpaca_live_cash_with_dedicated_live_keys_and_auth(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AUTONOMY_STAGE": "stage_5_full_autonomous_with_strict_caps",
                "ALPACA_LIVE_CASH_AUTONOMY_AUTH": "ENABLE_ALPACA_LIVE_CASH_AUTONOMY",
                "ALPACA_BASE_URL": "https://api.alpaca.markets",
                "ALPACA_LIVE_API_KEY_ID": "live-key",
                "ALPACA_LIVE_API_SECRET_KEY": "live-secret",
                "STOCK_BRIDGE_MAX_DAILY_LOSS": "2",
                "STOCK_BRIDGE_MAX_ORDER_NOTIONAL": "25",
            },
            clear=False,
        ):
            config = parse_args(["--broker", "alpaca", "--live", "--once"])

        self.assertTrue(config.live)
        self.assertEqual(config.broker, "alpaca")
        self.assertEqual(config.alpaca_api_key_id, "live-key")
        self.assertEqual(config.alpaca_api_secret_key, "live-secret")

    def test_parse_args_refuses_alpaca_live_without_dedicated_live_keys(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AUTONOMY_STAGE": "stage_5_full_autonomous_with_strict_caps",
                "ALPACA_LIVE_CASH_AUTONOMY_AUTH": "ENABLE_ALPACA_LIVE_CASH_AUTONOMY",
                "ALPACA_BASE_URL": "https://api.alpaca.markets",
                "ALPACA_API_KEY_ID": "generic-key",
                "ALPACA_API_SECRET_KEY": "generic-secret",
                "ALPACA_LIVE_API_KEY_ID": "",
                "ALPACA_LIVE_API_SECRET_KEY": "",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(SystemExit, "dedicated ALPACA_LIVE_API_KEY_ID"):
                parse_args(["--broker", "alpaca", "--live", "--once"])

    def test_parse_args_still_requires_auth_for_robinhood_live(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AUTONOMY_STAGE": "stage_3_human_approved_live_trades",
                "STOCK_BRIDGE_LIVE_AUTH": "",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(SystemExit, "Live mode refused"):
                parse_args(["--broker", "robinhood", "--live", "--once"])

    def test_parse_args_allows_stage_three_robinhood_inside_caps_with_auth(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AUTONOMY_STAGE": "stage_3_human_approved_live_trades",
                "STOCK_BRIDGE_LIVE_AUTH": "ENABLE_AGENTIC_STOCK_BRIDGE",
                "STOCK_BRIDGE_MAX_DAILY_LOSS": "5",
                "STOCK_BRIDGE_MAX_ORDER_NOTIONAL": "10",
            },
            clear=False,
        ):
            config = parse_args(["--broker", "robinhood", "--live", "--once"])

        self.assertTrue(config.live)
        self.assertEqual(config.max_daily_loss, 5)
        self.assertEqual(config.max_order_notional, 10)

    def test_parse_args_refuses_stage_three_order_cap_violation(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AUTONOMY_STAGE": "stage_3_human_approved_live_trades",
                "STOCK_BRIDGE_LIVE_AUTH": "ENABLE_AGENTIC_STOCK_BRIDGE",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(SystemExit, "max_order_notional"):
                parse_args(["--broker", "robinhood", "--live", "--once", "--max-order-notional", "25", "--max-daily-loss", "5"])

    def test_parse_args_refuses_stage_three_daily_loss_cap_violation(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AUTONOMY_STAGE": "stage_3_human_approved_live_trades",
                "STOCK_BRIDGE_LIVE_AUTH": "ENABLE_AGENTIC_STOCK_BRIDGE",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(SystemExit, "max_daily_loss"):
                parse_args(["--broker", "robinhood", "--live", "--once", "--max-order-notional", "10", "--max-daily-loss", "20"])


if __name__ == "__main__":
    unittest.main()
