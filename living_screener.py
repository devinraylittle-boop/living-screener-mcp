from __future__ import annotations

from app.factory import create_container


def run_market_scan(mode: str, tickers: list[str] | None = None, risk_level: str = "normal") -> dict:
    del risk_level
    return create_container().scanner.run_market_scan(mode, tickers)


def generate_trade_plan(ticker: str, direction: str, account_size: float, max_risk_dollars: float, setup_notes: str) -> dict:
    from app.mcp_server import generate_trade_plan as build_plan

    return build_plan(ticker, direction, "manual", account_size, max_risk_dollars, notes=setup_notes)


def check_risk_limits(ticker: str, proposed_risk_dollars: float, account_value: float, is_options_trade: bool, is_zero_dte: bool, has_earnings_within_48h: bool) -> dict:
    del has_earnings_within_48h
    from app.mcp_server import check_risk_limits as check_plan

    return check_plan({"ticker": ticker, "direction": "call" if is_options_trade else "long", "account_value": account_value, "proposed_risk_dollars": proposed_risk_dollars, "is_options_trade": is_options_trade, "is_zero_dte": is_zero_dte})
