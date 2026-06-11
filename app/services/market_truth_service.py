from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import Settings
from app.data_adapters.base import MarketDataAdapter
from app.storage.repositories import EventRepository
from app.version import BUILD_VERSION


class MarketTruthService:
    def __init__(self, settings: Settings, events: EventRepository, market_data: MarketDataAdapter | None, options: Any):
        self.settings = settings
        self.events = events
        self.market_data = market_data
        self.options = options

    def truth_source_status(self) -> dict[str, Any]:
        options_status = self.options.options_data_status()
        payload = {
            "status": "TRUTH_SOURCE_STATUS_READY",
            "schema_version": "truth_source_status_v1",
            "build_version": BUILD_VERSION,
            "market_data": {
                "provider": self.market_data.name if self.market_data else "none",
                "configured_provider": self.settings.market_data_provider,
                "has_finnhub_api_key": bool(self.settings.finnhub_api_key),
                "feed_type": "equity_quote_and_candle_review",
                "cash_ready": bool(self.market_data),
            },
            "options_data": options_status,
            "cash_readiness": {
                "cash_ready": False,
                "reason": "Real-money readiness still requires in-session market health, catalyst context, and fresh options truth or broker snapshot.",
            },
            "blocked_for_cash_without": [
                "fresh market data health check",
                "fresh catalyst context",
                "REAL_MONEY_OPTIONS_TRUTH_READY or fresh broker snapshot",
                "manual risk guard",
                "manual approval outside MCP",
            ],
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }
        return self.events.log("truth_source_status", payload)

    def check_market_data_health(self, tickers: list[str] | None = None, max_tickers: int = 10) -> dict[str, Any]:
        universe = self._universe(tickers, max_tickers)
        if not self.market_data:
            payload = {
                "status": "MARKET_DATA_HEALTH_BLOCKED",
                "schema_version": "market_data_health_v1",
                "provider": "none",
                "checked_tickers": universe,
                "healthy_count": 0,
                "degraded_count": len(universe),
                "rows": [
                    {"ticker": ticker, "status": "NO_ADAPTER", "blocking_reasons": ["No market data adapter configured."]}
                    for ticker in universe
                ],
                "cash_ready": False,
                "review_only": True,
                "can_place_order_from_this_mcp": False,
            }
            return self.events.log("market_data_health", payload)

        rows = [self._ticker_health(ticker) for ticker in universe]
        healthy = [row for row in rows if row["status"] == "HEALTHY"]
        degraded = [row for row in rows if row["status"] != "HEALTHY"]
        status = "MARKET_DATA_HEALTHY" if rows and not degraded else "MARKET_DATA_DEGRADED" if healthy else "MARKET_DATA_HEALTH_BLOCKED"
        payload = {
            "status": status,
            "schema_version": "market_data_health_v1",
            "provider": self.market_data.name,
            "configured_provider": self.settings.market_data_provider,
            "checked_tickers": universe,
            "healthy_count": len(healthy),
            "degraded_count": len(degraded),
            "rows": rows,
            "cash_ready": status == "MARKET_DATA_HEALTHY",
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }
        return self.events.log("market_data_health", payload)

    def get_catalyst_context(self, ticker: str, lookback_days: int = 3, lookahead_days: int = 7) -> dict[str, Any]:
        symbol = ticker.upper().strip()
        if not symbol:
            return self._catalyst_unavailable(symbol, ["Ticker is required."])
        if not self.settings.finnhub_api_key:
            return self._catalyst_unavailable(symbol, ["FINNHUB_API_KEY missing; catalyst context cannot be trusted."])

        reasons: list[str] = []
        news = self._company_news(symbol, lookback_days)
        earnings = self._earnings_calendar(symbol, lookahead_days)
        if news is None:
            reasons.append("Company-news provider failed or returned invalid data.")
            news = []
        if earnings is None:
            reasons.append("Earnings-calendar provider failed or returned invalid data.")
            earnings = []

        risk_items = self._catalyst_risks(news, earnings)
        status = "CATALYST_CONTEXT_BLOCK" if risk_items else "CATALYST_CONTEXT_CLEAR"
        payload = {
            "status": status,
            "schema_version": "catalyst_context_v1",
            "ticker": symbol,
            "lookback_days": lookback_days,
            "lookahead_days": lookahead_days,
            "news_count": len(news),
            "earnings_count": len(earnings),
            "risk_items": risk_items,
            "blocking_reasons": reasons + [item["reason"] for item in risk_items],
            "cash_ready": status == "CATALYST_CONTEXT_CLEAR" and not reasons,
            "news_sample": news[:5],
            "earnings_sample": earnings[:5],
            "notes": [
                "Catalyst context is a guard, not a trade signal.",
                "If catalyst data is missing or risky, cash readiness should fail closed.",
            ],
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }
        return self.events.log("catalyst_context", payload)

    def _ticker_health(self, ticker: str) -> dict[str, Any]:
        reasons: list[str] = []
        quote_age_seconds = None
        candle_age_seconds = None
        quote = None
        candles = []
        try:
            quote = self.market_data.get_quote(ticker) if self.market_data else None
        except Exception:
            reasons.append("Quote request failed safely.")
        try:
            candles = self.market_data.get_candles(ticker, self.settings.market_data_interval, self.settings.market_data_period) if self.market_data else []
        except Exception:
            reasons.append("Candle request failed safely.")

        now = datetime.now(UTC)
        if quote is None or quote.price <= 0:
            reasons.append("Quote missing or invalid.")
        elif quote.timestamp:
            quote_ts = quote.timestamp.astimezone(UTC) if quote.timestamp.tzinfo else quote.timestamp.replace(tzinfo=UTC)
            quote_age_seconds = round((now - quote_ts).total_seconds(), 3)
            if quote_age_seconds > self.settings.regular_market_max_staleness_minutes * 60:
                reasons.append("Quote age exceeds regular-market freshness threshold.")
        else:
            reasons.append("Quote timestamp missing.")

        if len(candles) < self.settings.min_candle_count:
            reasons.append("Insufficient candle count.")
        elif candles[-1].timestamp:
            candle_ts = candles[-1].timestamp.astimezone(UTC) if candles[-1].timestamp.tzinfo else candles[-1].timestamp.replace(tzinfo=UTC)
            candle_age_seconds = round((now - candle_ts).total_seconds(), 3)
            if candle_age_seconds > self.settings.regular_market_max_staleness_minutes * 60:
                reasons.append("Candle age exceeds regular-market freshness threshold.")
        else:
            reasons.append("Latest candle timestamp missing.")

        return {
            "ticker": ticker.upper(),
            "status": "HEALTHY" if not reasons else "DEGRADED",
            "quote_age_seconds": quote_age_seconds,
            "candle_age_seconds": candle_age_seconds,
            "quote_provider": getattr(quote, "provider", None),
            "candle_provider": candles[-1].provider if candles else None,
            "candle_count": len(candles),
            "blocking_reasons": reasons,
        }

    def _company_news(self, ticker: str, lookback_days: int) -> list[dict[str, Any]] | None:
        today = datetime.now(UTC).date()
        start = today - timedelta(days=max(1, lookback_days))
        data = self._get_finnhub_json(
            "/company-news",
            {"symbol": ticker, "from": start.isoformat(), "to": today.isoformat()},
        )
        if not isinstance(data, list):
            return None
        output = []
        for item in data[:20]:
            if not isinstance(item, dict):
                continue
            output.append(
                {
                    "datetime_utc": self._news_time(item.get("datetime")),
                    "headline": str(item.get("headline") or ""),
                    "source": str(item.get("source") or ""),
                    "url": str(item.get("url") or ""),
                    "risk_keywords": self._risk_keywords(str(item.get("headline") or "")),
                }
            )
        return output

    def _earnings_calendar(self, ticker: str, lookahead_days: int) -> list[dict[str, Any]] | None:
        today = datetime.now(UTC).date()
        end = today + timedelta(days=max(1, lookahead_days))
        data = self._get_finnhub_json(
            "/calendar/earnings",
            {"symbol": ticker, "from": today.isoformat(), "to": end.isoformat()},
        )
        rows = data.get("earningsCalendar") if isinstance(data, dict) else None
        if rows is None:
            return None
        return [
            {
                "date": str(item.get("date") or ""),
                "hour": str(item.get("hour") or ""),
                "eps_estimate": item.get("epsEstimate"),
                "revenue_estimate": item.get("revenueEstimate"),
            }
            for item in rows
            if isinstance(item, dict)
        ]

    def _catalyst_risks(self, news: list[dict[str, Any]], earnings: list[dict[str, Any]]) -> list[dict[str, str]]:
        risks: list[dict[str, str]] = []
        if earnings:
            risks.append({"type": "earnings_window", "reason": "Upcoming earnings event detected."})
        for item in news:
            keywords = item.get("risk_keywords") or []
            if keywords:
                risks.append(
                    {
                        "type": "news_keyword",
                        "reason": f"Recent headline contains risk keywords: {', '.join(keywords)}.",
                    }
                )
        return risks

    def _risk_keywords(self, text: str) -> list[str]:
        lowered = text.lower()
        keywords = [
            "earnings", "guidance", "sec", "investigation", "lawsuit", "fda", "halt",
            "offering", "secondary", "downgrade", "upgrade", "merger", "acquisition",
            "split", "dividend", "bankruptcy", "recall", "resigns", "fraud",
        ]
        return [keyword for keyword in keywords if keyword in lowered]

    def _get_finnhub_json(self, path: str, params: dict[str, Any]) -> Any:
        query = dict(params)
        query["token"] = self.settings.finnhub_api_key
        request = Request(
            f"https://finnhub.io/api/v1{path}?{urlencode(query)}",
            headers={"Accept": "application/json", "User-Agent": "living-screener-mcp/0.2"},
        )
        with urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))

    def _catalyst_unavailable(self, ticker: str, reasons: list[str]) -> dict[str, Any]:
        payload = {
            "status": "CATALYST_CONTEXT_UNAVAILABLE",
            "schema_version": "catalyst_context_v1",
            "ticker": ticker,
            "blocking_reasons": reasons,
            "cash_ready": False,
            "news_sample": [],
            "earnings_sample": [],
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }
        return self.events.log("catalyst_context", payload)

    def _universe(self, tickers: list[str] | None, max_tickers: int) -> list[str]:
        raw = tickers or list(self.settings.scalp_watchlist)
        output: list[str] = []
        for ticker in raw:
            symbol = str(ticker).upper().strip()
            if symbol and symbol not in output:
                output.append(symbol)
            if len(output) >= max(1, min(max_tickers, self.settings.max_scan_universe)):
                break
        return output

    def _news_time(self, value: Any) -> str | None:
        try:
            return datetime.fromtimestamp(int(value), UTC).isoformat()
        except Exception:
            return None
