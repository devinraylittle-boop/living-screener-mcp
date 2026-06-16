import asyncio
import unittest
from typing import Any

from tools.stock_bridge_loop import AlpacaBroker, BridgeConfig, ExecutionRejected, RobinhoodBroker, state_scope


def run(coro):
    return asyncio.run(coro)


def config(**overrides: Any) -> BridgeConfig:
    values = {
        "broker": "alpaca",
        "base_url": "https://living-screener-mcp.onrender.com",
        "mcp_url": "https://agent.robinhood.com/mcp/trading",
        "account_number": "",
        "alpaca_base_url": "https://api.alpaca.markets",
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


class FakeAlpacaBroker(AlpacaBroker):
    def __init__(self, cfg: BridgeConfig, account: dict[str, Any] | None = None):
        super().__init__(cfg)
        self.account_payload = account or {
            "status": "ACTIVE",
            "trading_blocked": False,
            "options_approved_level": 3,
            "options_trading_level": 3,
            "crypto_status": "INACTIVE",
        }
        self.calls: list[dict[str, Any]] = []

    def _trading(self, path: str, method: str = "GET", payload: dict[str, Any] | None = None, timeout: int = 30):
        self.calls.append({"path": path, "method": method, "payload": payload})
        if path == "/v2/account":
            return self.account_payload
        if path.startswith("/v2/options/contracts"):
            return {
                "option_contracts": [
                    {
                        "symbol": "SPY260116C00600000",
                        "status": "active",
                        "tradable": True,
                        "underlying_symbol": "SPY",
                        "expiration_date": "2026-01-16",
                        "type": "call",
                        "strike_price": "600",
                    },
                    {
                        "symbol": "SPY260116C00610000",
                        "status": "inactive",
                        "tradable": True,
                        "underlying_symbol": "SPY",
                        "expiration_date": "2026-01-16",
                        "type": "call",
                        "strike_price": "610",
                    },
                ]
            }
        if path == "/v2/orders" and method == "POST":
            return {"id": "order-1", "status": "accepted", **(payload or {})}
        return {}


class AlpacaExecutionRouterTests(unittest.TestCase):
    def test_alpaca_base_url_accepts_optional_v2_suffix(self) -> None:
        cfg_without_suffix = config(alpaca_base_url="https://paper-api.alpaca.markets")
        cfg_with_suffix = config(alpaca_base_url="https://paper-api.alpaca.markets/v2")
        broker = FakeAlpacaBroker(cfg_with_suffix)

        self.assertEqual(broker.base_url, "https://paper-api.alpaca.markets")
        self.assertEqual(state_scope(cfg_with_suffix), state_scope(cfg_without_suffix))

    def test_stock_order_still_routes_to_stock_executor(self) -> None:
        broker = FakeAlpacaBroker(config())
        result = run(
            broker.place_order(
                {
                    "asset_class": "stock",
                    "symbol": "BAC",
                    "side": "buy",
                    "type": "market",
                    "dollar_amount": "2.00",
                    "time_in_force": "day",
                }
            )
        )
        self.assertEqual(result["asset_class"], "stock")
        self.assertEqual(broker.calls[-1]["path"], "/v2/orders")
        self.assertEqual(broker.calls[-1]["payload"]["notional"], "2.00")

    def test_option_buy_to_open_limit_order_routes_to_options_executor(self) -> None:
        broker = FakeAlpacaBroker(config())
        result = run(
            broker.place_order(
                {
                    "asset_class": "option",
                    "symbol": "SPY260116C00600000",
                    "quantity": "1",
                    "type": "limit",
                    "limit_price": "0.10",
                    "position_intent": "buy_to_open",
                }
            )
        )
        payload = broker.calls[-1]["payload"]
        self.assertEqual(result["asset_class"], "option")
        self.assertEqual(payload["symbol"], "SPY260116C00600000")
        self.assertEqual(payload["qty"], "1")
        self.assertEqual(payload["time_in_force"], "day")
        self.assertFalse(payload["extended_hours"])
        self.assertEqual(payload["order_class"], "simple")
        self.assertEqual(payload["position_intent"], "buy_to_open")

    def test_option_order_rejects_fractional_qty(self) -> None:
        broker = FakeAlpacaBroker(config())
        with self.assertRaisesRegex(ExecutionRejected, "fractional"):
            run(broker.review_order({"asset_class": "option", "symbol": "SPY260116C00600000", "quantity": "1.5", "type": "limit", "limit_price": "0.10"}))

    def test_option_order_rejects_notional(self) -> None:
        broker = FakeAlpacaBroker(config())
        with self.assertRaisesRegex(ExecutionRejected, "notional"):
            run(broker.review_order({"asset_class": "option", "symbol": "SPY260116C00600000", "dollar_amount": "10", "quantity": "1", "type": "limit", "limit_price": "0.10"}))

    def test_option_order_rejects_missing_limit_price(self) -> None:
        broker = FakeAlpacaBroker(config())
        with self.assertRaisesRegex(ExecutionRejected, "limit_price"):
            run(broker.review_order({"asset_class": "option", "symbol": "SPY260116C00600000", "quantity": "1", "side": "buy", "type": "limit"}))

    def test_crypto_inactive_does_not_block_stock_or_options(self) -> None:
        broker = FakeAlpacaBroker(config(), account={"options_approved_level": 3, "options_trading_level": 3, "crypto_status": "INACTIVE"})
        stock = run(broker.review_order({"asset_class": "stock", "symbol": "BAC", "side": "buy", "type": "market", "dollar_amount": "2"}))
        option = run(broker.review_order({"asset_class": "option", "symbol": "SPY260116C00600000", "quantity": "1", "type": "limit", "limit_price": "0.10", "position_intent": "buy_to_open"}))
        self.assertEqual(stock["asset_class"], "stock")
        self.assertEqual(option["asset_class"], "option")

    def test_crypto_order_rejected_while_enable_crypto_execution_false(self) -> None:
        broker = FakeAlpacaBroker(config(enable_crypto_execution=False), account={"crypto_status": "ACTIVE"})
        with self.assertRaisesRegex(ExecutionRejected, "disabled"):
            run(broker.review_order({"asset_class": "crypto", "symbol": "BTC/USD", "side": "buy", "type": "market", "dollar_amount": "5"}))

    def test_crypto_market_order_rejected_by_default_even_when_crypto_active(self) -> None:
        broker = FakeAlpacaBroker(config(enable_crypto_execution=True), account={"crypto_status": "ACTIVE"})
        with self.assertRaisesRegex(ExecutionRejected, "Market crypto orders are disabled"):
            run(broker.review_order({"asset_class": "crypto", "symbol": "BTC/USD", "side": "buy", "type": "market", "dollar_amount": "5"}))

    def test_crypto_limit_order_routes_through_same_alpaca_orders_endpoint(self) -> None:
        broker = FakeAlpacaBroker(config(enable_crypto_execution=True), account={"crypto_status": "ACTIVE"})
        result = run(
            broker.review_order(
                {
                    "asset_class": "crypto",
                    "symbol": "BTC/USD",
                    "side": "buy",
                    "type": "limit",
                    "dollar_amount": "5",
                    "limit_price": "65000",
                    "time_in_force": "gtc",
                }
            )
        )
        self.assertEqual(result["asset_class"], "crypto")
        self.assertEqual(result["normalized_intent"]["symbol"], "BTC/USD")
        self.assertEqual(result["normalized_intent"]["notional"], "5")
        self.assertEqual(result["normalized_intent"]["limit_price"], "65000")

    def test_crypto_order_rejects_qty_and_notional_together(self) -> None:
        broker = FakeAlpacaBroker(config(enable_crypto_execution=True), account={"crypto_status": "ACTIVE"})
        with self.assertRaisesRegex(ExecutionRejected, "either notional"):
            run(
                broker.review_order(
                    {
                        "asset_class": "crypto",
                        "symbol": "BTC/USD",
                        "side": "buy",
                        "type": "limit",
                        "dollar_amount": "5",
                        "quantity": "0.001",
                        "limit_price": "65000",
                    }
                )
            )

    def test_robinhood_capabilities_mark_missing_options_and_crypto_tools(self) -> None:
        broker = RobinhoodBroker(config())
        broker.tools = {
            "get_portfolio",
            "get_equity_positions",
            "get_equity_orders",
            "get_equity_quotes",
            "get_equity_tradability",
            "review_equity_order",
            "place_equity_order",
            "cancel_equity_order",
        }
        capabilities = broker.capabilities()
        self.assertTrue(capabilities["equity_order"]["ready"])
        self.assertFalse(capabilities["options"]["ready"])
        self.assertEqual(capabilities["options_status"], "ROLLING_OUT_OR_NOT_EXPOSED")
        self.assertFalse(capabilities["crypto"]["ready"])
        self.assertEqual(capabilities["crypto_status"], "NOT_EXPOSED_BY_CURRENT_MCP")

    def test_contract_lookup_returns_active_tradable_exact_contract(self) -> None:
        broker = FakeAlpacaBroker(config())
        symbol = run(broker.lookup_option_contract("SPY", "2026-01-16", "call", "600"))
        self.assertEqual(symbol, "SPY260116C00600000")


if __name__ == "__main__":
    unittest.main()
