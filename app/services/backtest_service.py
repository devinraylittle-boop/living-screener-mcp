from __future__ import annotations

from statistics import mean
from typing import Any

from app.config import Settings
from app.storage.repositories import EventRepository


class BacktestService:
    def __init__(self, events: EventRepository, settings: Settings | None = None):
        self.events = events
        self.settings = settings or Settings()

    def run_backtest(self, engine: str, tickers: list[str], start: str, end: str, config_overrides: dict | None = None) -> dict:
        samples = []
        errors = []
        overrides = config_overrides or {}
        for ticker in [item.upper() for item in tickers]:
            try:
                samples.extend(self._ticker_samples(engine, ticker, start, end, overrides))
            except Exception as exc:
                errors.append({"ticker": ticker, "error": type(exc).__name__})

        candidate_samples = [sample for sample in samples if sample["decision"] == "CANDIDATE"]
        returns = [sample["forward_return_close"] for sample in candidate_samples if sample["forward_return_close"] is not None]
        expectancy = round(mean(returns), 5) if returns else 0
        result = {
            "engine": engine,
            "tickers": [t.upper() for t in tickers],
            "start": start,
            "end": end,
            "no_lookahead_bias": True,
            "sample_size": len(samples),
            "candidate_sample_size": len(candidate_samples),
            "watch_only_sample_size": len([sample for sample in samples if sample["decision"] == "WATCH_ONLY"]),
            "expectancy": expectancy,
            "win_rate": round(sum(1 for value in returns if value > 0) / len(returns), 4) if returns else 0,
            "horizon_summary": self._horizon_summary(candidate_samples),
            "mfe_mae_summary": self._mfe_mae_summary(candidate_samples),
            "applied_config": {
                "candidate_score_threshold": self._threshold(engine, overrides),
                "relative_volume_floor": self._relative_volume_floor(engine, overrides),
                "relative_volume_gate_applied": self._is_scalp_engine(engine),
            },
            "overfitting_risk": "high" if len(candidate_samples) < 30 else "medium" if len(candidate_samples) < 100 else "unknown",
            "samples_preview": samples[:25],
            "errors": errors,
            "notes": "Rolling signal audit. Signals use candles available at the signal timestamp; later candles are used only for outcome grading.",
        }
        return self.events.log("backtest", result)

    def _ticker_samples(self, engine: str, ticker: str, start: str, end: str, overrides: dict[str, Any]) -> list[dict[str, Any]]:
        import yfinance as yf

        interval = str(overrides.get("interval", "5m"))
        threshold = self._threshold(engine, overrides)
        relative_volume_floor = self._relative_volume_floor(engine, overrides)
        window = int(overrides.get("window", 12))
        step = int(overrides.get("step", 12))
        forward_bars = int(overrides.get("forward_bars", 12))
        horizons = self._horizons(forward_bars, overrides)
        max_horizon = max(horizons.values())
        history = yf.Ticker(ticker).history(start=start, end=end, interval=interval, prepost=False)
        if history is None or history.empty or len(history) < window + max_horizon + 1:
            return []

        samples: list[dict[str, Any]] = []
        rows = list(history.iterrows())
        for index in range(window, len(rows) - max_horizon, step):
            window_rows = rows[index - window : index]
            signal_time, signal_row = rows[index]
            future = rows[index + forward_bars][1]
            closes = [self._float(row.get("Close")) for _, row in window_rows]
            volumes = [self._int(row.get("Volume")) or 0 for _, row in window_rows]
            if any(value is None or value <= 0 for value in closes):
                continue
            signal_close = self._float(signal_row.get("Close"))
            future_close = self._float(future.get("Close"))
            if signal_close is None or signal_close <= 0 or future_close is None:
                continue
            relative_volume = self._relative_volume(volumes)
            score = self._score(closes, volumes, signal_close, scalp=self._is_scalp_engine(engine))
            if score < threshold:
                decision = "PASS"
            elif self._is_scalp_engine(engine) and relative_volume < relative_volume_floor:
                decision = "WATCH_ONLY"
            else:
                decision = "CANDIDATE"
            samples.append(
                {
                    "ticker": ticker,
                    "timestamp": self._timestamp(signal_time),
                    "score": score,
                    "decision": decision,
                    "relative_volume": round(relative_volume, 2),
                    "relative_volume_floor": relative_volume_floor if self._is_scalp_engine(engine) else None,
                    "entry_reference": round(signal_close, 4),
                    "forward_bars": forward_bars,
                    "forward_return_close": round((future_close - signal_close) / signal_close, 5),
                    "forward_returns": self._forward_returns(rows, index, signal_close, horizons),
                    "max_favorable_excursion": self._excursion(rows[index : index + forward_bars + 1], signal_close, favorable=True),
                    "max_adverse_excursion": self._excursion(rows[index : index + forward_bars + 1], signal_close, favorable=False),
                }
            )
        return samples

    def _score(self, closes: list[float], volumes: list[int], signal_close: float, scalp: bool = False) -> float:
        trend_pct = (closes[-1] - closes[0]) / closes[0]
        recent = closes[-5:] if len(closes) >= 5 else closes
        recent_trend_pct = (recent[-1] - recent[0]) / recent[0]
        relative_volume = self._relative_volume(volumes)
        if scalp:
            return self._scalp_score(closes, volumes, signal_close, trend_pct, recent_trend_pct, relative_volume)
        score = 0.0
        if trend_pct > 0.015:
            score += 22
        if recent_trend_pct > 0.004:
            score += 18
        if signal_close > mean(closes):
            score += 15
        if relative_volume >= 1.2:
            score += 15
        if signal_close > closes[-1]:
            score += 10
        if sum(volumes) >= 1_000_000:
            score += 10
        if abs(trend_pct) < 0.004:
            score -= 20
        return round(max(0.0, min(100.0, score)), 2)

    def _scalp_score(self, closes: list[float], volumes: list[int], signal_close: float, trend_pct: float, recent_trend_pct: float, relative_volume: float) -> float:
        pct_change = (signal_close - closes[-1]) / closes[-1] if closes[-1] else 0.0
        score = 0.0
        if abs(pct_change) >= self.settings.scalp_min_abs_change_pct:
            score += 20
        if abs(trend_pct) >= 0.008:
            score += 18
        if abs(recent_trend_pct) >= 0.003:
            score += 16
        if relative_volume >= self.settings.scalp_min_relative_volume:
            score += 18
        if (trend_pct >= 0 and signal_close > mean(closes)) or (trend_pct < 0 and signal_close < mean(closes)):
            score += 12
        if sum(volumes) >= self.settings.min_equity_volume * 2:
            score += 10
        if abs(pct_change) < self.settings.scalp_min_abs_change_pct and relative_volume < self.settings.scalp_min_relative_volume:
            score -= 18
        return round(max(0.0, min(100.0, score)), 2)

    def _relative_volume(self, volumes: list[int]) -> float:
        average_volume = mean(volumes[:-1]) if len(volumes) > 1 and mean(volumes[:-1]) > 0 else 0
        return volumes[-1] / average_volume if average_volume else 0.0

    def _threshold(self, engine: str, overrides: dict[str, Any]) -> float:
        default = self.settings.scalp_candidate_score_threshold if self._is_scalp_engine(engine) else self.settings.candidate_score_threshold
        return float(overrides.get("candidate_score_threshold", overrides.get("score_threshold", default)))

    def _relative_volume_floor(self, engine: str, overrides: dict[str, Any]) -> float:
        if not self._is_scalp_engine(engine):
            return 0.0
        return float(overrides.get("relative_volume_floor", overrides.get("scalp_min_relative_volume", self.settings.scalp_min_relative_volume)))

    def _is_scalp_engine(self, engine: str) -> bool:
        return "scalp" in engine.lower() or "mover" in engine.lower()

    def _horizons(self, forward_bars: int, overrides: dict[str, Any]) -> dict[str, int]:
        custom = overrides.get("horizons")
        if isinstance(custom, dict):
            return {str(key): max(1, int(value)) for key, value in custom.items()}
        return {"15m": 3, "30m": 6, "1h": 12, "close": forward_bars}

    def _forward_returns(self, rows: list[Any], index: int, entry: float, horizons: dict[str, int]) -> dict[str, float | None]:
        output: dict[str, float | None] = {}
        for label, bars in horizons.items():
            if index + bars >= len(rows):
                output[label] = None
                continue
            close = self._float(rows[index + bars][1].get("Close"))
            output[label] = round((close - entry) / entry, 5) if close is not None and entry > 0 else None
        return output

    def _horizon_summary(self, samples: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
        labels = sorted({label for sample in samples for label in sample.get("forward_returns", {}).keys()})
        summary = {}
        for label in labels:
            values = [sample["forward_returns"][label] for sample in samples if sample.get("forward_returns", {}).get(label) is not None]
            summary[label] = {
                "sample_size": len(values),
                "win_rate": round(sum(1 for value in values if value > 0) / len(values), 4) if values else 0,
                "expectancy": round(mean(values), 5) if values else 0,
            }
        return summary

    def _mfe_mae_summary(self, samples: list[dict[str, Any]]) -> dict[str, float]:
        mfe = [sample["max_favorable_excursion"] for sample in samples if sample.get("max_favorable_excursion") is not None]
        mae = [sample["max_adverse_excursion"] for sample in samples if sample.get("max_adverse_excursion") is not None]
        return {
            "avg_max_favorable_excursion": round(mean(mfe), 5) if mfe else 0,
            "avg_max_adverse_excursion": round(mean(mae), 5) if mae else 0,
        }

    def _excursion(self, rows: list[Any], entry: float, favorable: bool) -> float | None:
        values = []
        for _, row in rows:
            value = self._float(row.get("High" if favorable else "Low"))
            if value is not None:
                values.append((value - entry) / entry)
        if not values:
            return None
        return round((max(values) if favorable else min(values)), 5)

    def _timestamp(self, value: Any) -> str:
        return value.isoformat() if hasattr(value, "isoformat") else str(value)

    def _float(self, value: Any) -> float | None:
        try:
            return None if value is None or value != value else float(value)
        except Exception:
            return None

    def _int(self, value: Any) -> int | None:
        try:
            return None if value is None or value != value else int(value)
        except Exception:
            return None
