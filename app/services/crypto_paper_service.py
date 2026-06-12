from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import mean
from typing import Any

from app.storage.repositories import EventRepository


@dataclass(frozen=True)
class CryptoPaperRules:
    starting_cash: float = 5.0
    take_profit_pct: float = 0.0035
    stop_loss_pct: float = 0.0025
    breakeven_trigger_pct: float = 0.002
    max_hold_bars: int = 12
    min_relative_volume: float = 1.05
    fast_window: int = 5
    slow_window: int = 20
    trend_window: int = 48
    max_late_spike_extension_pct: float = 0.004
    late_spike_relative_volume: float = 2.5
    max_reclaim_extension_pct: float = 0.003
    fee_bps: float = 0.0


class CryptoPaperService:
    robinhood_crypto_symbols = (
        "BTC-USD", "ETH-USD", "DOGE-USD", "LTC-USD", "SHIB-USD", "ZRX-USD", "AAVE-USD", "AERO-USD",
        "ALGO-USD", "ARB-USD", "ASTER-USD", "AVAX-USD", "AVNT-USD", "AXS-USD", "BAT-USD", "BIO-USD",
        "BCH-USD", "BNB-USD", "BONK-USD", "CC-USD", "ADA-USD", "MEW-USD", "LINK-USD", "COMP-USD",
        "ATOM-USD", "CRV-USD", "WIF-USD", "EIGEN-USD", "ENA-USD", "ETC-USD", "FLR-USD", "FLOKI-USD",
        "USDG-USD", "HBAR-USD", "HYPE-USD", "IMX-USD", "JTO-USD", "ZRO-USD", "LDO-USD", "LIT-USD",
        "MNT-USD", "SYRUP-USD", "MEGA-USD", "MOODENG-USD", "NEAR-USD", "TRUMP-USD", "ONDO-USD",
        "XCN-USD", "OP-USD", "ORCA-USD", "PAXG-USD", "PNUT-USD", "PEPE-USD", "XPL-USD", "DOT-USD",
        "POPCAT-USD", "PENGU-USD", "PYTH-USD", "QNT-USD", "RAY-USD", "RENDER-USD", "SKR-USD",
        "SEI-USD", "SKY-USD", "SOL-USD", "STRK-USD", "SUI-USD", "XLM-USD", "SNX-USD", "XTZ-USD",
        "GRT-USD", "TON-USD", "UNI-USD", "USDC-USD", "CHIP-USD", "VVV-USD", "VIRTUAL-USD",
        "WLFI-USD", "W-USD", "XRP-USD", "ZEC-USD", "ZORA-USD",
    )
    default_symbols = robinhood_crypto_symbols
    core_live_symbols = ("BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "DOGE-USD", "ADA-USD", "AVAX-USD", "LINK-USD", "LTC-USD", "BCH-USD")
    liquid_live_symbols = robinhood_crypto_symbols

    def __init__(self, events: EventRepository):
        self.events = events

    def universe(self) -> dict[str, Any]:
        core = set(self.core_live_symbols)
        symbols = list(self.robinhood_crypto_symbols)
        return {
            "status": "ROBINHOOD_CRYPTO_UNIVERSE_READY",
            "schema_version": "robinhood_crypto_universe_v1",
            "source": "Robinhood Crypto availability supported-crypto table",
            "tradable_symbol_count": len(symbols),
            "general_consideration_count": len(symbols),
            "symbols": symbols,
            "tiers": {
                "core_liquid_first_pass": [symbol for symbol in symbols if symbol in core],
                "full_universe_watch": [symbol for symbol in symbols if symbol not in core],
            },
            "policy": [
                "Every Robinhood-supported tradable crypto is in general consideration.",
                "General consideration is not approval; each asset must pass data, liquidity, spread, fee, slippage, setup, and account-size gates.",
                "Assets without usable candle/quote/order-book data remain WATCH_ONLY until proof exists.",
            ],
            "review_only": True,
            "can_place_order_from_this_mcp": False,
        }

    def start_session(self, starting_cash: float = 5.0, symbols: list[str] | None = None, duration_hours: int = 8, interval_minutes: int = 15) -> dict:
        payload = {
            "status": "PAPER_SESSION_READY",
            "mode": "crypto_paper_only",
            "starting_cash": round(float(starting_cash), 2),
            "symbols": self._symbols(symbols),
            "duration_hours": int(duration_hours),
            "interval_minutes": int(interval_minutes),
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
            "background_worker_started": False,
            "instructions": "Render web requests are not an always-on worker. Re-run crypto paper backtests periodically or in the morning to review hypothetical results.",
            "rules": self.rules().__dict__,
        }
        return self.events.log("crypto_paper_session", payload)

    def rules(self, starting_cash: float = 5.0, overrides: dict[str, Any] | None = None) -> CryptoPaperRules:
        raw = dict(overrides or {})
        profile = str(raw.pop("profile", "strict")).lower()
        profile_overrides: dict[str, Any] = {}
        if profile == "balanced":
            profile_overrides = {
                "min_relative_volume": 0.95,
                "trend_window": 36,
                "max_reclaim_extension_pct": 0.004,
                "max_late_spike_extension_pct": 0.005,
                "late_spike_relative_volume": 3.0,
            }
        elif profile == "exploratory":
            profile_overrides = {
                "min_relative_volume": 0.90,
                "trend_window": 30,
                "max_reclaim_extension_pct": 0.005,
                "max_late_spike_extension_pct": 0.006,
                "late_spike_relative_volume": 3.5,
            }

        values = {**profile_overrides, **raw}
        allowed = set(CryptoPaperRules.__dataclass_fields__.keys())
        values = {key: value for key, value in values.items() if key in allowed and key != "starting_cash"}
        return CryptoPaperRules(starting_cash=float(starting_cash), **values)

    def run_backtest(self, symbols: list[str] | None = None, period: str = "1d", interval: str = "5m", starting_cash: float = 5.0, max_trades_per_symbol: int = 50, rule_overrides: dict[str, Any] | None = None) -> dict:
        rules = self.rules(starting_cash, rule_overrides)
        overrides = rule_overrides or {}
        excluded = {str(symbol).upper().strip() for symbol in overrides.get("exclude_symbols", [])}
        selected_symbols = [symbol for symbol in self._symbols(symbols) if symbol not in excluded]
        results = []
        for symbol in selected_symbols:
            candles = self._load_yfinance_candles(symbol, period, interval)
            if len(candles) < rules.slow_window + 2:
                results.append(
                    {
                        "symbol": symbol,
                        "status": "PASS",
                        "reason": "Not enough candle data for crypto paper backtest.",
                        "trade_count": 0,
                    }
                )
                continue
            results.append(self._simulate_symbol(symbol, candles, rules, max_trades_per_symbol))

        tradable = [item for item in results if item.get("status") == "BACKTEST_COMPLETE"]
        best = sorted(tradable, key=lambda item: (item["return_pct"], item["win_rate"], -item["max_drawdown_pct"]), reverse=True)
        aggregate = self._aggregate_results(results, float(starting_cash))
        payload = {
            "status": "CRYPTO_PAPER_BACKTEST_COMPLETE",
            "result": self._verdict(aggregate),
            "mode": "paper_only_no_broker_execution",
            "period": period,
            "interval": interval,
            "starting_cash": round(float(starting_cash), 2),
            "symbols": selected_symbols,
            "excluded_symbols": sorted(excluded),
            "best_symbol": best[0]["symbol"] if best else None,
            "aggregate": aggregate,
            "results": results,
            "rules": rules.__dict__,
            "rule_overrides": rule_overrides or {},
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
            "no_lookahead_bias": True,
            "warnings": [
                "This is a paper/backtest result only, not a live trade instruction.",
                "Crypto trades overnight and can gap or whipsaw; real broker execution is intentionally unavailable here.",
            ],
            "model_notes": [
                "Long entries require a broader uptrend, fast average above slow average, and a controlled reclaim rather than a late spike chase.",
                "High relative-volume candles that are already extended from recent price are skipped as likely exhaustion.",
                "If a trade goes green enough to trigger breakeven protection and then fades, the paper model exits instead of waiting for the full stop.",
                "Symbol recommendations identify carriers, leaks, and no-trade watches for future basket selection; they are not live trade instructions.",
            ],
        }
        return self.events.log("crypto_paper_backtest", payload)

    def live_test_gate(
        self,
        symbols: list[str] | None = None,
        starting_cash: float = 5.0,
        intended_cash: float = 5.0,
        account_balance: float | None = None,
        buying_power: float | None = None,
        exchange_connected: bool = False,
        open_positions_checked: bool = False,
        open_position_count: int | None = None,
        open_orders_checked: bool = False,
        open_order_count: int | None = None,
        market_data_fresh: bool = False,
        order_book_fresh: bool = False,
        kill_switch_ready: bool = False,
        emergency_shutdown_ready: bool = False,
        daily_loss_lockout_clear: bool = False,
        journaling_ready: bool = True,
        fee_bps: float | None = None,
        slippage_pct: float | None = None,
        min_order_size: float | None = None,
        candidate_snapshots: dict[str, dict[str, Any]] | None = None,
        max_spread_pct: float = 0.0015,
        max_fee_impact_pct: float = 0.0015,
        max_slippage_pct: float = 0.0015,
        min_24h_volume: float = 100_000_000.0,
        target_profit_pct: float | None = None,
        stop_loss_pct: float | None = None,
        emergency_max_loss: float | None = None,
        backtest_symbol_limit: int = 20,
        period: str = "1d",
        interval: str = "5m",
    ) -> dict:
        rule_overrides: dict[str, Any] = {"fee_bps": fee_bps or 0.0}
        if target_profit_pct is not None:
            rule_overrides["take_profit_pct"] = target_profit_pct
        if stop_loss_pct is not None:
            rule_overrides["stop_loss_pct"] = stop_loss_pct
        rules = self.rules(starting_cash, rule_overrides)
        selected_symbols = [symbol for symbol in self._symbols(symbols) if symbol in self.liquid_live_symbols]
        excluded_symbols = [symbol for symbol in self._symbols(symbols) if symbol not in self.liquid_live_symbols]
        snapshots = {str(key).upper(): value for key, value in (candidate_snapshots or {}).items() if isinstance(value, dict)}
        prioritized_symbols = self._prioritize_symbols(selected_symbols, snapshots, max(1, int(backtest_symbol_limit)))
        backtest = self.run_backtest(prioritized_symbols, period, interval, starting_cash, 20, rule_overrides)
        exchange_gates = self._exchange_gates(
            account_balance=account_balance,
            buying_power=buying_power,
            intended_cash=intended_cash,
            exchange_connected=exchange_connected,
            open_positions_checked=open_positions_checked,
            open_position_count=open_position_count,
            open_orders_checked=open_orders_checked,
            open_order_count=open_order_count,
            market_data_fresh=market_data_fresh,
            order_book_fresh=order_book_fresh,
            kill_switch_ready=kill_switch_ready,
            emergency_shutdown_ready=emergency_shutdown_ready,
            daily_loss_lockout_clear=daily_loss_lockout_clear,
            journaling_ready=journaling_ready,
            min_order_size=min_order_size,
        )
        candidates = []
        results_by_symbol = {str(result.get("symbol") or "").upper(): result for result in backtest.get("results", [])}
        for symbol in selected_symbols:
            result = results_by_symbol.get(symbol) or {
                "symbol": symbol,
                "status": "UNSCANNED",
                "symbol_recommendation": "WATCH_ONLY",
                "trade_count": 0,
                "win_rate": 0.0,
                "return_pct": 0.0,
                "reason": "Included in Robinhood full universe, but skipped by current backtest resource limit or unavailable market-data adapter.",
            }
            snapshot = snapshots.get(symbol) or {}
            if fee_bps is not None and "fee_bps" not in snapshot:
                snapshot["fee_bps"] = fee_bps
            if slippage_pct is not None and "slippage_pct" not in snapshot:
                snapshot["slippage_pct"] = slippage_pct
            if min_order_size is not None and "min_order_size" not in snapshot:
                snapshot["min_order_size"] = min_order_size
            candidate = self._classify_live_candidate(
                result,
                snapshot,
                rules,
                intended_cash,
                float(account_balance or starting_cash),
                max_spread_pct,
                max_fee_impact_pct,
                max_slippage_pct,
                min_24h_volume,
            )
            candidates.append(candidate)

        approved = [item for item in candidates if item["classification"] == "AUTONOMOUS_CRYPTO_APPROVED"]
        final_decision = self._final_live_decision(exchange_gates, approved, candidates)
        payload = {
            "status": "CRYPTO_LIVE_TEST_GATE_READY",
            "schema_version": "crypto_live_test_gate_v1",
            "final_decision": final_decision,
            "mode": "separate_exchange_executor_required",
            "starting_cash": round(float(starting_cash), 2),
            "intended_cash": round(float(intended_cash), 2),
            "allowed_symbols": list(self.liquid_live_symbols),
            "selected_symbols": selected_symbols,
            "universe": {
                "general_consideration_count": len(self.robinhood_crypto_symbols),
                "selected_symbol_count": len(selected_symbols),
                "backtested_symbol_count": len(prioritized_symbols),
                "backtested_symbols": prioritized_symbols,
            },
            "excluded_symbols": excluded_symbols,
            "exchange_gates": exchange_gates,
            "risk_controls": {
                "planned_target_pct": rules.take_profit_pct,
                "planned_stop_loss_pct": rules.stop_loss_pct,
                "planned_trade_max_loss": round(float(intended_cash) * rules.stop_loss_pct, 4),
                "emergency_account_max_loss": None if emergency_max_loss is None else round(float(emergency_max_loss), 4),
                "emergency_shutdown_note": "Emergency max loss is an account shutdown, not permission to risk that much on one scalp.",
            },
            "candidate_classifications": candidates,
            "approved_candidate_count": len(approved),
            "best_candidate": approved[0] if approved else (candidates[0] if candidates else None),
            "backtest_summary": {
                "result": backtest.get("result"),
                "aggregate": backtest.get("aggregate"),
                "best_symbol": backtest.get("best_symbol"),
            },
            "absolute_rules": [
                "No leverage, margin, futures, options, or market orders from this MCP.",
                "PASS if exchange, balance, open-order, open-position, market-data, order-book, fee, spread, slippage, stop, target, kill-switch, or journal proof is missing.",
                "Only AUTONOMOUS_CRYPTO_APPROVED candidates may be handed to a separate exchange executor.",
                "This MCP still cannot place, submit, simulate, modify, or cancel orders.",
            ],
            "next_action": self._crypto_next_action(final_decision),
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }
        return self.events.log("crypto_live_test_gate", payload)

    def run_autonomous_cycle(
        self,
        symbols: list[str] | None = None,
        starting_cash: float = 5.0,
        intended_cash: float = 5.0,
        account_balance: float | None = None,
        buying_power: float | None = None,
        exchange_connected: bool = False,
        open_positions_checked: bool = False,
        open_position_count: int | None = None,
        open_orders_checked: bool = False,
        open_order_count: int | None = None,
        market_data_fresh: bool = False,
        order_book_fresh: bool = False,
        kill_switch_ready: bool = False,
        emergency_shutdown_ready: bool = False,
        daily_loss_lockout_clear: bool = False,
        journaling_ready: bool = True,
        fee_bps: float | None = None,
        slippage_pct: float | None = None,
        min_order_size: float | None = None,
        candidate_snapshots: dict[str, dict[str, Any]] | None = None,
        max_spread_pct: float = 0.0015,
        max_fee_impact_pct: float = 0.0015,
        max_slippage_pct: float = 0.0015,
        min_24h_volume: float = 100_000_000.0,
        target_profit_pct: float | None = None,
        stop_loss_pct: float | None = None,
        emergency_max_loss: float | None = None,
        backtest_symbol_limit: int = 20,
        execution_mode: str = "paper",
        max_open_positions: int = 1,
        period: str = "1d",
        interval: str = "5m",
    ) -> dict:
        normalized_snapshots = {str(key).upper(): value for key, value in (candidate_snapshots or {}).items() if isinstance(value, dict)}
        open_positions = self._open_autonomous_positions()
        management_actions = [self._manage_autonomous_position(position, normalized_snapshots) for position in open_positions]
        still_open = [position for position, action in zip(open_positions, management_actions) if action.get("action") != "PAPER_CLOSE"]
        if len(still_open) >= max(1, int(max_open_positions)):
            payload = {
                "status": "CRYPTO_AUTONOMOUS_POSITION_MANAGEMENT_ONLY",
                "schema_version": "crypto_autonomous_cycle_v1",
                "execution_mode": execution_mode,
                "open_positions": still_open,
                "management_actions": management_actions,
                "new_entry": None,
                "final_decision": "POSITION_LIMIT_REACHED",
                "review_only": True,
                "can_place_order_from_this_mcp": False,
                "can_cancel_order_from_this_mcp": False,
            }
            return self.events.log("crypto_autonomous_cycle", payload)

        gate = self.live_test_gate(
            symbols=symbols,
            starting_cash=starting_cash,
            intended_cash=intended_cash,
            account_balance=account_balance,
            buying_power=buying_power,
            exchange_connected=exchange_connected,
            open_positions_checked=open_positions_checked,
            open_position_count=open_position_count,
            open_orders_checked=open_orders_checked,
            open_order_count=open_order_count,
            market_data_fresh=market_data_fresh,
            order_book_fresh=order_book_fresh,
            kill_switch_ready=kill_switch_ready,
            emergency_shutdown_ready=emergency_shutdown_ready,
            daily_loss_lockout_clear=daily_loss_lockout_clear,
            journaling_ready=journaling_ready,
            fee_bps=fee_bps,
            slippage_pct=slippage_pct,
            min_order_size=min_order_size,
            candidate_snapshots=normalized_snapshots,
            max_spread_pct=max_spread_pct,
            max_fee_impact_pct=max_fee_impact_pct,
            max_slippage_pct=max_slippage_pct,
            min_24h_volume=min_24h_volume,
            target_profit_pct=target_profit_pct,
            stop_loss_pct=stop_loss_pct,
            emergency_max_loss=emergency_max_loss,
            backtest_symbol_limit=backtest_symbol_limit,
            period=period,
            interval=interval,
        )
        approved = [item for item in gate.get("candidate_classifications", []) if item.get("classification") == "AUTONOMOUS_CRYPTO_APPROVED"]
        mode = str(execution_mode or "paper").lower().strip()
        new_entry = None
        final_decision = gate.get("final_decision")
        if approved and gate.get("final_decision") == "LIMITED_AUTONOMOUS_CRYPTO_ENABLED":
            ticket = approved[0]["order_ticket"]
            if mode == "paper":
                new_entry = self._open_autonomous_paper_position(ticket, gate.get("risk_controls") or {}, gate.get("id"))
                final_decision = "PAPER_POSITION_OPENED"
            else:
                new_entry = {
                    "status": "LIVE_EXECUTOR_HANDOFF_READY",
                    "ticket": ticket,
                    "notes": [
                        "Separate exchange executor required.",
                        "This MCP cannot place, submit, modify, simulate, or cancel orders.",
                        "Use limit-only execution and cancel if the ticket no longer matches the live screen.",
                    ],
                }
                final_decision = "LIVE_EXECUTOR_HANDOFF_READY"

        payload = {
            "status": "CRYPTO_AUTONOMOUS_CYCLE_COMPLETE",
            "schema_version": "crypto_autonomous_cycle_v1",
            "execution_mode": mode,
            "gate_decision": gate.get("final_decision"),
            "final_decision": final_decision,
            "open_positions_before": open_positions,
            "management_actions": management_actions,
            "new_entry": new_entry,
            "gate": gate,
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }
        return self.events.log("crypto_autonomous_cycle", payload)

    def summarize_live_test_report(
        self,
        starting_balance: float = 5.0,
        ending_balance: float | None = None,
        fees_paid: float = 0.0,
        estimated_slippage: float = 0.0,
        live_trades: list[dict[str, Any]] | None = None,
        rejected_candidates: list[dict[str, Any]] | None = None,
        limit_events: int = 100,
    ) -> dict:
        live_trades = list(live_trades or [])
        rejected_candidates = list(rejected_candidates or [])
        recent_gates = self.events.recent("crypto_live_test_gate", limit_events)
        last_gate = recent_gates[0]["payload"] if recent_gates else {}
        if not rejected_candidates:
            rejected_candidates = [
                item for item in (last_gate.get("candidate_classifications") or [])
                if item.get("classification") != "AUTONOMOUS_CRYPTO_APPROVED"
            ]
        ending = float(ending_balance) if ending_balance is not None else float(starting_balance)
        pnl = ending - float(starting_balance)
        best_live_trade = max(live_trades, key=lambda item: float(item.get("pnl_dollars", 0.0)), default=None)
        worst_live_trade = min(live_trades, key=lambda item: float(item.get("pnl_dollars", 0.0)), default=None)
        payload = {
            "status": "CRYPTO_LIVE_TEST_REPORT_READY",
            "schema_version": "crypto_live_test_report_v1",
            "starting_balance": round(float(starting_balance), 2),
            "ending_balance": round(ending, 4),
            "total_profit_loss": round(pnl, 4),
            "trade_count": len(live_trades),
            "rejected_candidate_count": len(rejected_candidates),
            "best_rejected_candidate": rejected_candidates[0] if rejected_candidates else None,
            "worst_rejected_candidate": rejected_candidates[-1] if rejected_candidates else None,
            "best_live_trade": best_live_trade,
            "worst_live_trade": worst_live_trade,
            "fees_paid": round(float(fees_paid), 4),
            "estimated_slippage": round(float(estimated_slippage), 4),
            "execution_quality": self._quality_label(live_trades, "execution_quality", "UNPROVEN_NO_LIVE_TRADES"),
            "data_quality": self._quality_label([last_gate], "exchange_gates", "UNKNOWN"),
            "strategy_quality": self._strategy_quality(last_gate, live_trades),
            "did_follow_rules": not any(str(trade.get("rule_violation") or "").strip() for trade in live_trades),
            "did_force_trades": any(str(trade.get("forced_trade") or "").lower() in {"1", "true", "yes"} for trade in live_trades),
            "protected_account": pnl >= -0.25,
            "tomorrow_stock_options_improvements": [
                "Keep broker/order/position proof separate from scanner confidence.",
                "Require receipt-quality fills, fees, and slippage before learning from live outcomes.",
                "Keep noisy crypto learning separate from equity/options cash gates.",
            ],
            "module_decisions": {
                "crypto_scanner": "LIMITED_REVIEW",
                "crypto_live_execution": "DISABLED_UNLESS_SEPARATE_EXECUTOR_AND_ALL_GATES_PASS",
                "stocks_options_scanner": "REVIEW_ONLY",
                "options_cash_gate": "BROKER_SNAPSHOT_REQUIRED",
                "learning": "ENABLED_PROPOSALS_ONLY",
            },
            "final_decision_for_tomorrow": "REVIEW_ONLY" if pnl < 0 or len(live_trades) == 0 else "LIMITED_AUTONOMOUS_CRYPTO_ENABLED",
            "last_gate_decision": last_gate.get("final_decision"),
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }
        return self.events.log("crypto_live_test_report", payload)

    def _open_autonomous_positions(self, limit_events: int = 200) -> list[dict[str, Any]]:
        closed = {
            str(event["payload"].get("trade_id"))
            for event in self.events.recent("crypto_autonomous_paper_close", limit_events)
            if event.get("payload", {}).get("trade_id")
        }
        positions = []
        for event in self.events.recent("crypto_autonomous_paper_open", limit_events):
            payload = dict(event.get("payload") or {})
            trade_id = str(payload.get("trade_id") or "")
            if trade_id and trade_id not in closed:
                positions.append(payload)
        return positions

    def _manage_autonomous_position(self, position: dict[str, Any], snapshots: dict[str, dict[str, Any]]) -> dict[str, Any]:
        symbol = str(position.get("symbol") or "").upper()
        snapshot = snapshots.get(symbol) or {}
        price = self._snapshot_exit_price(snapshot)
        if price is None:
            return {"action": "HOLD", "trade_id": position.get("trade_id"), "symbol": symbol, "reason": "No fresh exit price supplied."}
        target = self._float(position.get("target_price"))
        stop = self._float(position.get("stop_price"))
        entry = self._float(position.get("entry_price")) or price
        exit_reason = None
        if target is not None and price >= target:
            exit_reason = "target_hit"
        elif stop is not None and price <= stop:
            exit_reason = "stop_hit"
        elif str(snapshot.get("setup_failed") or "").lower() in {"1", "true", "yes"}:
            exit_reason = "setup_failed"
        elif str(snapshot.get("spread_unsafe") or "").lower() in {"1", "true", "yes"}:
            exit_reason = "spread_unsafe"
        if not exit_reason:
            return {
                "action": "HOLD",
                "trade_id": position.get("trade_id"),
                "symbol": symbol,
                "current_price": round(price, 8),
                "unrealized_return_pct": round((price - entry) / entry, 6) if entry else 0.0,
            }
        close_payload = {
            "status": "PAPER_POSITION_CLOSED",
            "trade_id": position.get("trade_id"),
            "symbol": symbol,
            "entry_price": entry,
            "exit_price": round(price, 8),
            "exit_reason": exit_reason,
            "size_units": position.get("size_units"),
            "entry_cash": position.get("entry_cash"),
            "return_pct": round((price - entry) / entry, 6) if entry else 0.0,
            "pnl_dollars": round(float(position.get("entry_cash") or 0.0) * ((price - entry) / entry), 4) if entry else 0.0,
            "timestamp": datetime.now(UTC).isoformat(),
            "paper_only": True,
            "can_place_order_from_this_mcp": False,
        }
        logged = self.events.log("crypto_autonomous_paper_close", close_payload)
        return {"action": "PAPER_CLOSE", "logged_event_id": logged["id"], **close_payload}

    def _open_autonomous_paper_position(self, ticket: dict[str, Any], risk_controls: dict[str, Any], gate_event_id: int | None) -> dict[str, Any]:
        symbol = str(ticket.get("coin_pair") or "").upper()
        entry = self._float(ticket.get("intended_limit_price") or ticket.get("mid") or ticket.get("ask"))
        entry_cash = self._float(ticket.get("position_size")) or 0.0
        target_pct = self._float(risk_controls.get("planned_target_pct")) or self.rules().take_profit_pct
        stop_pct = self._float(risk_controls.get("planned_stop_loss_pct")) or self.rules().stop_loss_pct
        timestamp = datetime.now(UTC).isoformat()
        trade_id = f"{symbol}-{timestamp}"
        payload = {
            "status": "PAPER_POSITION_OPEN",
            "trade_id": trade_id,
            "symbol": symbol,
            "entry_price": entry,
            "entry_cash": round(entry_cash, 4),
            "size_units": round(entry_cash / entry, 10) if entry and entry > 0 else 0.0,
            "target_price": round(entry * (1 + target_pct), 8) if entry else None,
            "stop_price": round(entry * (1 - stop_pct), 8) if entry else None,
            "target_pct": target_pct,
            "stop_loss_pct": stop_pct,
            "gate_event_id": gate_event_id,
            "ticket": ticket,
            "timestamp": timestamp,
            "paper_only": True,
            "can_place_order_from_this_mcp": False,
        }
        return self.events.log("crypto_autonomous_paper_open", payload)

    def _snapshot_exit_price(self, snapshot: dict[str, Any]) -> float | None:
        return self._float(snapshot.get("bid") or snapshot.get("last") or snapshot.get("mid") or snapshot.get("ask"))

    def _exchange_gates(
        self,
        account_balance: float | None,
        buying_power: float | None,
        intended_cash: float,
        exchange_connected: bool,
        open_positions_checked: bool,
        open_position_count: int | None,
        open_orders_checked: bool,
        open_order_count: int | None,
        market_data_fresh: bool,
        order_book_fresh: bool,
        kill_switch_ready: bool,
        emergency_shutdown_ready: bool,
        daily_loss_lockout_clear: bool,
        journaling_ready: bool,
        min_order_size: float | None,
    ) -> dict[str, Any]:
        checks = {
            "exchange_connected": bool(exchange_connected),
            "cash_balance_confirmed": account_balance is not None and float(account_balance) >= intended_cash,
            "buying_power_confirmed": buying_power is not None and float(buying_power) >= intended_cash,
            "open_positions_checked": bool(open_positions_checked) and open_position_count is not None,
            "open_orders_checked": bool(open_orders_checked) and open_order_count is not None,
            "no_existing_orders": open_order_count in {0, None} and bool(open_orders_checked),
            "fresh_market_data": bool(market_data_fresh),
            "fresh_order_book": bool(order_book_fresh),
            "minimum_order_size_known": min_order_size is not None and float(min_order_size) <= intended_cash,
            "kill_switch_ready": bool(kill_switch_ready),
            "daily_loss_lockout_clear": bool(daily_loss_lockout_clear),
            "emergency_shutdown_ready": bool(emergency_shutdown_ready),
            "journaling_ready": bool(journaling_ready),
        }
        blockers = [name for name, passed in checks.items() if not passed]
        return {
            "status": "EXCHANGE_PROOF_READY" if not blockers else "EXCHANGE_PROOF_INCOMPLETE",
            "checks": checks,
            "blockers": blockers,
            "account_balance": None if account_balance is None else round(float(account_balance), 4),
            "buying_power": None if buying_power is None else round(float(buying_power), 4),
            "open_position_count": open_position_count,
            "open_order_count": open_order_count,
        }

    def _classify_live_candidate(
        self,
        result: dict[str, Any],
        snapshot: dict[str, Any],
        rules: CryptoPaperRules,
        intended_cash: float,
        account_balance: float,
        max_spread_pct: float,
        max_fee_impact_pct: float,
        max_slippage_pct: float,
        min_24h_volume: float,
    ) -> dict[str, Any]:
        symbol = str(result.get("symbol") or "").upper()
        reasons: list[str] = []
        recommendation = result.get("symbol_recommendation")
        if recommendation != "PAPER_ELIGIBLE":
            classification = "WATCH_ONLY" if recommendation == "WATCH_ONLY" or result.get("status") == "UNSCANNED" else ("LIQUID_BUT_NO_EDGE" if result.get("status") == "BACKTEST_COMPLETE" else "PASS")
            reasons.append(f"Backtest recommendation is {recommendation or result.get('status')}.")
        elif not snapshot:
            classification = "WATCH_ONLY"
            reasons.append("No fresh broker/exchange quote and order-book snapshot supplied.")
        else:
            classification = "SMALL_ACCOUNT_CRYPTO_ACCEPTABLE"

        bid = self._float(snapshot.get("bid"))
        ask = self._float(snapshot.get("ask"))
        mid = ((bid + ask) / 2) if bid and ask else self._float(snapshot.get("mid") or snapshot.get("last"))
        spread_pct = ((ask - bid) / mid) if bid and ask and mid else None
        volume_24h = self._float(snapshot.get("volume_24h") or snapshot.get("quote_volume_24h"))
        fee_bps = self._float(snapshot.get("fee_bps")) or 0.0
        fee_impact_pct = (fee_bps * 2) / 10000
        slippage = self._float(snapshot.get("slippage_pct"))
        min_order = self._float(snapshot.get("min_order_size"))
        if snapshot:
            if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
                classification = "EDGE_VISIBLE_BUT_ORDER_UNSAFE"
                reasons.append("Bid/ask snapshot is missing or contradictory.")
            elif spread_pct is None or spread_pct > max_spread_pct:
                classification = "SPREAD_TOO_WIDE"
                reasons.append("Spread exceeds small-account crypto limit.")
            elif volume_24h is None or volume_24h < min_24h_volume:
                classification = "HIGH_RISK_MANUAL_ONLY"
                reasons.append("24-hour liquidity is below the live-test threshold.")
            elif fee_impact_pct > max_fee_impact_pct or fee_impact_pct >= rules.take_profit_pct * 0.5:
                classification = "FEES_DESTROY_EDGE"
                reasons.append("Round-trip fee impact consumes too much of the target.")
            elif slippage is None or slippage > max_slippage_pct:
                classification = "SLIPPAGE_TOO_HIGH"
                reasons.append("Slippage estimate is missing or too high.")
            elif min_order is None or min_order > intended_cash:
                classification = "EDGE_VISIBLE_BUT_ORDER_UNSAFE"
                reasons.append("Minimum order size is missing or above intended cash.")
            elif classification == "SMALL_ACCOUNT_CRYPTO_ACCEPTABLE":
                classification = "AUTONOMOUS_CRYPTO_APPROVED"

        ticket = self._build_crypto_order_ticket(
            symbol,
            result,
            snapshot,
            rules,
            intended_cash,
            account_balance,
            classification,
            reasons,
            spread_pct,
            fee_impact_pct,
            slippage,
        )
        return {
            "symbol": symbol,
            "classification": classification,
            "setup_type": "trend_or_reclaim_continuation",
            "direction": "long",
            "setup_score": self._score_from_result(result),
            "liquidity_score": self._liquidity_score(volume_24h, min_24h_volume),
            "spread_score": self._spread_score(spread_pct, max_spread_pct),
            "fee_impact_score": self._fee_score(fee_impact_pct, max_fee_impact_pct),
            "slippage_estimate": slippage,
            "account_suitability_score": 100 if intended_cash <= account_balance and intended_cash <= 5.0 else 60,
            "confidence_score": self._confidence_score(classification, result),
            "approval_or_rejection_reasons": reasons,
            "order_ticket": ticket,
        }

    def _build_crypto_order_ticket(
        self,
        symbol: str,
        result: dict[str, Any],
        snapshot: dict[str, Any],
        rules: CryptoPaperRules,
        intended_cash: float,
        account_balance: float,
        classification: str,
        reasons: list[str],
        spread_pct: float | None,
        fee_impact_pct: float,
        slippage: float | None,
    ) -> dict[str, Any]:
        bid = self._float(snapshot.get("bid"))
        ask = self._float(snapshot.get("ask"))
        mid = ((bid + ask) / 2) if bid and ask else self._float(snapshot.get("mid") or snapshot.get("last"))
        limit_price = ask if ask else mid
        max_fill = (limit_price * (1 + (slippage or 0.0))) if limit_price else None
        gross_reward = intended_cash * rules.take_profit_pct
        fee_estimate = intended_cash * fee_impact_pct
        max_loss = intended_cash * rules.stop_loss_pct + fee_estimate
        expected_reward = gross_reward - fee_estimate
        ticket = {
            "coin_pair": symbol,
            "direction": "long",
            "asset_type": "spot_crypto",
            "bid": bid,
            "ask": ask,
            "mid": None if mid is None else round(mid, 8),
            "intended_limit_price": None if limit_price is None else round(limit_price, 8),
            "max_acceptable_fill_price": None if max_fill is None else round(max_fill, 8),
            "spread_percentage": None if spread_pct is None else round(spread_pct, 6),
            "volume_24h": self._float(snapshot.get("volume_24h") or snapshot.get("quote_volume_24h")),
            "recent_volume_expansion": result.get("win_rate"),
            "liquidity_grade": "A" if classification == "AUTONOMOUS_CRYPTO_APPROVED" else "UNPROVEN",
            "fee_estimate": round(fee_estimate, 4),
            "slippage_estimate": slippage,
            "setup_reason": "Paper model found controlled continuation/reclaim behavior." if result.get("symbol_recommendation") == "PAPER_ELIGIBLE" else "No live edge approved.",
            "entry_trigger": "Limit buy only after fresh bid/ask and order book remain inside ticket limits.",
            "stop_invalidation": f"Exit if price moves -{rules.stop_loss_pct:.2%}, reclaim fails, data becomes stale, spread widens, or kill switch triggers.",
            "profit_target": f"Exit mechanically near +{rules.take_profit_pct:.2%} before fees/slippage turn the scalp stale.",
            "max_loss": round(max_loss, 4),
            "expected_reward": round(expected_reward, 4),
            "account_balance_before_trade": round(account_balance, 4),
            "position_size": round(intended_cash, 4),
            "final_risk_percentage": round(max_loss / account_balance, 4) if account_balance > 0 else None,
            "final_verdict": classification if classification == "AUTONOMOUS_CRYPTO_APPROVED" else "REJECTED",
            "rejection_reasons": reasons,
            "can_place_order_from_this_mcp": False,
        }
        return ticket

    def _final_live_decision(self, exchange_gates: dict[str, Any], approved: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> str:
        if exchange_gates["status"] != "EXCHANGE_PROOF_READY":
            return "REVIEW_ONLY"
        if not candidates:
            return "PASS"
        if not approved:
            return "NO_TRADE_PLAN"
        return "LIMITED_AUTONOMOUS_CRYPTO_ENABLED"

    def _crypto_next_action(self, decision: str) -> str:
        if decision == "LIMITED_AUTONOMOUS_CRYPTO_ENABLED":
            return "Hand the top approved ticket to a separate exchange executor only after the user verifies the exact venue and live ticket."
        if decision == "NO_TRADE_PLAN":
            return "Do not trade. Keep scanning and log rejected candidates for learning."
        return "Stay review-only until every exchange, data, order-book, fee, slippage, kill-switch, and journal proof is supplied."

    def _score_from_result(self, result: dict[str, Any]) -> int:
        if result.get("symbol_recommendation") == "PAPER_ELIGIBLE":
            return min(100, 70 + int(float(result.get("win_rate", 0.0)) * 20) + max(0, int(float(result.get("return_pct", 0.0)) * 1000)))
        return 40

    def _liquidity_score(self, volume_24h: float | None, min_24h_volume: float) -> int:
        if volume_24h is None:
            return 0
        return min(100, int((volume_24h / min_24h_volume) * 80))

    def _spread_score(self, spread_pct: float | None, max_spread_pct: float) -> int:
        if spread_pct is None or spread_pct <= 0:
            return 0
        return max(0, min(100, int(100 * (1 - spread_pct / max_spread_pct))))

    def _fee_score(self, fee_impact_pct: float, max_fee_impact_pct: float) -> int:
        return max(0, min(100, int(100 * (1 - fee_impact_pct / max_fee_impact_pct)))) if max_fee_impact_pct > 0 else 0

    def _confidence_score(self, classification: str, result: dict[str, Any]) -> int:
        if classification == "AUTONOMOUS_CRYPTO_APPROVED":
            return min(95, 75 + int(float(result.get("win_rate", 0.0)) * 20))
        if classification == "SMALL_ACCOUNT_CRYPTO_ACCEPTABLE":
            return 65
        if classification in {"WATCH_ONLY", "LIQUID_BUT_NO_EDGE"}:
            return 45
        return 20

    def _quality_label(self, items: list[dict[str, Any]], key: str, empty: str) -> str:
        if not items:
            return empty
        if key == "exchange_gates":
            gates = items[0].get(key) or {}
            return "PROVEN" if gates.get("status") == "EXCHANGE_PROOF_READY" else "INCOMPLETE"
        return "LOGGED"

    def _strategy_quality(self, last_gate: dict[str, Any], live_trades: list[dict[str, Any]]) -> str:
        if live_trades:
            wins = [trade for trade in live_trades if float(trade.get("pnl_dollars", 0.0)) > 0]
            return "PROMISING_SMALL_SAMPLE" if wins else "NEEDS_REVIEW"
        if last_gate.get("final_decision") in {"PASS", "NO_TRADE_PLAN", "REVIEW_ONLY"}:
            return "DISCIPLINED_ABSTENTION"
        return "UNPROVEN"

    def _prioritize_symbols(self, selected_symbols: list[str], snapshots: dict[str, dict[str, Any]], limit: int) -> list[str]:
        priority = []
        for symbol in snapshots:
            if symbol in selected_symbols and symbol not in priority:
                priority.append(symbol)
        for symbol in self.core_live_symbols:
            if symbol in selected_symbols and symbol not in priority:
                priority.append(symbol)
        for symbol in selected_symbols:
            if symbol not in priority:
                priority.append(symbol)
        return priority[: max(1, int(limit))]

    def _simulate_symbol(self, symbol: str, candles: list[dict[str, Any]], rules: CryptoPaperRules, max_trades: int) -> dict:
        cash = rules.starting_cash
        equity_high = cash
        max_drawdown_pct = 0.0
        trades: list[dict[str, Any]] = []
        position: dict[str, Any] | None = None

        for index in range(rules.slow_window + 1, len(candles)):
            candle = candles[index]
            closes = [float(item["close"]) for item in candles[:index]]
            volumes = [float(item["volume"]) for item in candles[:index]]
            fast = mean(closes[-rules.fast_window :])
            slow = mean(closes[-rules.slow_window :])
            prior_fast = mean(closes[-rules.fast_window - 1 : -1])
            prior_slow = mean(closes[-rules.slow_window - 1 : -1])
            relative_volume = 0.0 if len(volumes) < rules.slow_window or mean(volumes[-rules.slow_window :]) <= 0 else float(candle["volume"]) / mean(volumes[-rules.slow_window :])
            price = float(candle["close"])
            recent_anchor = mean(closes[-6:]) if len(closes) >= 6 else closes[-1]
            recent_extension_pct = (price - recent_anchor) / recent_anchor if recent_anchor else 0.0
            recent_reclaim_pct = (price - closes[-1]) / closes[-1] if closes[-1] else 0.0
            trend_anchor = closes[-min(len(closes), rules.trend_window)]
            broader_trend_pct = (closes[-1] - trend_anchor) / trend_anchor if trend_anchor else 0.0

            if position is None and len(trades) < max_trades:
                crosses_up = prior_fast <= prior_slow and fast > slow
                trend_ok = broader_trend_pct > 0
                not_late_spike = not (
                    relative_volume >= rules.late_spike_relative_volume
                    and recent_extension_pct > rules.max_late_spike_extension_pct
                )
                controlled_reclaim = 0 < recent_reclaim_pct <= rules.max_reclaim_extension_pct
                if crosses_up and trend_ok and not_late_spike and controlled_reclaim and relative_volume >= rules.min_relative_volume:
                    fee = cash * rules.fee_bps / 10000
                    size = max(cash - fee, 0.0) / price
                    position = {
                        "entry_time": candle["timestamp"],
                        "entry_price": price,
                        "size": size,
                        "entry_index": index,
                        "relative_volume": round(relative_volume, 3),
                        "max_favorable_pct": 0.0,
                        "broader_trend_pct": round(broader_trend_pct, 5),
                        "recent_extension_pct": round(recent_extension_pct, 5),
                    }
                    cash = 0.0
                continue

            if position is None:
                continue

            entry = float(position["entry_price"])
            change_pct = (price - entry) / entry
            position["max_favorable_pct"] = max(float(position.get("max_favorable_pct", 0.0)), change_pct)
            hold_bars = index - int(position["entry_index"])
            exit_reason = None
            if change_pct >= rules.take_profit_pct:
                exit_reason = "take_profit"
            elif float(position.get("max_favorable_pct", 0.0)) >= rules.breakeven_trigger_pct and change_pct <= 0:
                exit_reason = "breakeven_fade"
            elif change_pct <= -rules.stop_loss_pct:
                exit_reason = "stop_loss"
            elif hold_bars >= rules.max_hold_bars:
                exit_reason = "max_hold"
            elif fast < slow:
                exit_reason = "signal_fade"

            if exit_reason:
                gross = float(position["size"]) * price
                fee = gross * rules.fee_bps / 10000
                cash = max(gross - fee, 0.0)
                equity_high = max(equity_high, cash)
                if equity_high > 0:
                    max_drawdown_pct = min(max_drawdown_pct, (cash - equity_high) / equity_high)
                trades.append(
                    {
                        "symbol": symbol,
                        "entry_time": position["entry_time"],
                        "exit_time": candle["timestamp"],
                        "entry_price": round(entry, 6),
                        "exit_price": round(price, 6),
                        "return_pct": round(change_pct, 5),
                        "pnl_dollars": round(cash - rules.starting_cash if len(trades) == 0 else cash - trades[-1]["ending_cash"], 4),
                        "ending_cash": round(cash, 4),
                        "exit_reason": exit_reason,
                        "entry_relative_volume": position["relative_volume"],
                        "entry_broader_trend_pct": position["broader_trend_pct"],
                        "entry_recent_extension_pct": position["recent_extension_pct"],
                    }
                )
                position = None

        if position is not None:
            last = candles[-1]
            price = float(last["close"])
            cash = float(position["size"]) * price
            trades.append(
                {
                    "symbol": symbol,
                    "entry_time": position["entry_time"],
                    "exit_time": last["timestamp"],
                    "entry_price": round(float(position["entry_price"]), 6),
                    "exit_price": round(price, 6),
                    "return_pct": round((price - float(position["entry_price"])) / float(position["entry_price"]), 5),
                    "pnl_dollars": round(cash - rules.starting_cash if len(trades) == 0 else cash - trades[-1]["ending_cash"], 4),
                    "ending_cash": round(cash, 4),
                    "exit_reason": "session_end",
                    "entry_relative_volume": position["relative_volume"],
                    "entry_broader_trend_pct": position["broader_trend_pct"],
                    "entry_recent_extension_pct": position["recent_extension_pct"],
                }
            )

        wins = [trade for trade in trades if trade["return_pct"] > 0]
        exit_reason_counts: dict[str, int] = {}
        for trade in trades:
            reason = str(trade["exit_reason"])
            exit_reason_counts[reason] = exit_reason_counts.get(reason, 0) + 1
        ending_cash = cash if trades else rules.starting_cash
        return {
            "symbol": symbol,
            "status": "BACKTEST_COMPLETE",
            "symbol_recommendation": self._symbol_recommendation(len(trades), ending_cash, rules.starting_cash, len(wins), exit_reason_counts),
            "starting_cash": round(rules.starting_cash, 2),
            "ending_cash": round(ending_cash, 4),
            "return_pct": round((ending_cash - rules.starting_cash) / rules.starting_cash, 5) if rules.starting_cash > 0 else 0.0,
            "trade_count": len(trades),
            "winning_trade_count": len(wins),
            "stop_loss_count": exit_reason_counts.get("stop_loss", 0),
            "exit_reason_counts": exit_reason_counts,
            "win_rate": round(len(wins) / len(trades), 4) if trades else 0.0,
            "max_drawdown_pct": round(max_drawdown_pct, 5),
            "sample_trades": trades[:10],
        }

    def _aggregate_results(self, results: list[dict[str, Any]], starting_cash: float) -> dict:
        completed = [item for item in results if item.get("status") == "BACKTEST_COMPLETE"]
        eligible_symbols = [item["symbol"] for item in completed if item.get("symbol_recommendation") == "PAPER_ELIGIBLE"]
        leak_symbols = [item["symbol"] for item in completed if item.get("symbol_recommendation") == "LEAK"]
        no_trade_symbols = [item["symbol"] for item in completed if item.get("symbol_recommendation") == "NO_TRADE_WATCH"]
        total_trade_count = sum(int(item.get("trade_count", 0)) for item in completed)
        total_starting_cash = starting_cash * len(completed)
        total_ending_cash = sum(float(item.get("ending_cash", starting_cash)) for item in completed)
        wins = sum(
            int(item["winning_trade_count"])
            if "winning_trade_count" in item
            else sum(1 for trade in item.get("sample_trades", []) if float(trade.get("return_pct", 0)) > 0)
            for item in completed
        )
        stop_losses = sum(
            int(item["stop_loss_count"])
            if "stop_loss_count" in item
            else sum(1 for trade in item.get("sample_trades", []) if trade.get("exit_reason") == "stop_loss")
            for item in completed
        )
        positive_symbols = sum(1 for item in completed if float(item.get("return_pct", 0)) > 0 and int(item.get("trade_count", 0)) > 0)
        max_drawdown = min((float(item.get("max_drawdown_pct", 0.0)) for item in completed), default=0.0)
        exit_reason_counts: dict[str, int] = {}
        for item in completed:
            for reason, count in (item.get("exit_reason_counts") or {}).items():
                exit_reason_counts[reason] = exit_reason_counts.get(reason, 0) + int(count)
        return {
            "symbol_count": len(completed),
            "total_trade_count": total_trade_count,
            "total_starting_cash": round(total_starting_cash, 2),
            "total_ending_cash": round(total_ending_cash, 4),
            "aggregate_return_pct": round((total_ending_cash - total_starting_cash) / total_starting_cash, 5) if total_starting_cash > 0 else 0.0,
            "win_rate": round(wins / total_trade_count, 4) if total_trade_count else 0.0,
            "stop_loss_frequency": round(stop_losses / total_trade_count, 4) if total_trade_count else 0.0,
            "max_drawdown_pct": round(max_drawdown, 5),
            "exit_reason_counts": exit_reason_counts,
            "positive_symbol_count": positive_symbols,
            "eligible_symbols": eligible_symbols,
            "leak_symbols": leak_symbols,
            "no_trade_symbols": no_trade_symbols,
            "adaptive_candidate_symbols": eligible_symbols,
        }

    def _verdict(self, aggregate: dict) -> str:
        if aggregate["positive_symbol_count"] >= 2 and aggregate["total_trade_count"] > 5 and aggregate["aggregate_return_pct"] > 0:
            return "PAPER_WATCH"
        return "PASS"

    def _symbol_recommendation(self, trade_count: int, ending_cash: float, starting_cash: float, wins: int, exit_reason_counts: dict[str, int]) -> str:
        if trade_count == 0:
            return "NO_TRADE_WATCH"
        return_pct = (ending_cash - starting_cash) / starting_cash if starting_cash > 0 else 0.0
        win_rate = wins / trade_count if trade_count else 0.0
        stop_loss_frequency = exit_reason_counts.get("stop_loss", 0) / trade_count if trade_count else 0.0
        if return_pct > 0 and win_rate >= 0.5 and stop_loss_frequency <= 0.25:
            return "PAPER_ELIGIBLE"
        if return_pct < 0:
            return "LEAK"
        return "WATCH_ONLY"

    def _load_yfinance_candles(self, symbol: str, period: str, interval: str) -> list[dict[str, Any]]:
        import yfinance as yf

        history = yf.Ticker(symbol).history(period=period, interval=interval, prepost=True)
        if history is None or history.empty:
            return []
        candles = []
        for timestamp, row in history.iterrows():
            close = self._float(row.get("Close"))
            volume = self._float(row.get("Volume")) or 0.0
            if close is None or close <= 0:
                continue
            candles.append(
                {
                    "timestamp": self._timestamp(timestamp),
                    "close": close,
                    "volume": volume,
                }
            )
        return candles

    def _symbols(self, symbols: list[str] | None) -> list[str]:
        raw = symbols or list(self.default_symbols)
        output = []
        for symbol in raw:
            normalized = symbol.upper().strip()
            if normalized and normalized not in output:
                output.append(normalized)
        return output

    def _float(self, value: Any) -> float | None:
        try:
            return None if value is None or value != value else float(value)
        except Exception:
            return None

    def _timestamp(self, value: Any) -> str:
        if hasattr(value, "to_pydatetime"):
            value = value.to_pydatetime()
        if isinstance(value, datetime):
            timestamp = value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
            return timestamp.isoformat()
        return datetime.now(UTC).isoformat()
