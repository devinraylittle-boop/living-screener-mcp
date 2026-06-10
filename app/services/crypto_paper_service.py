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
    default_symbols = ("BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD")

    def __init__(self, events: EventRepository):
        self.events = events

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
        return output[:12]

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
