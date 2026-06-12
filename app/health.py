from __future__ import annotations

from starlette.responses import JSONResponse

from app.config import Settings
from app.storage.database import Database
from app.version import BUILD_VERSION


async def health(request):
    settings: Settings = request.app.state.settings
    Database(settings.database_path).init()
    return JSONResponse({"status": "ok", "service": settings.app_name, "build_version": BUILD_VERSION, "review_only": settings.review_only, "place_orders": settings.place_orders, "database": "ok"})


async def safe_config(request):
    settings: Settings = request.app.state.settings
    return JSONResponse(
        {
            "service": settings.app_name,
            "build_version": BUILD_VERSION,
            "environment": settings.environment,
            "hosted_mode": settings.hosted_mode,
            "review_only": settings.review_only,
            "place_orders": settings.place_orders,
            "market_orders_allowed": settings.market_orders_allowed,
            "manual_approval_required": settings.manual_approval_required,
            "pending_buy_recheck_seconds": settings.pending_buy_recheck_seconds,
            "max_pending_order_price_drift_pct": settings.max_pending_order_price_drift_pct,
            "market_data_provider": settings.market_data_provider,
            "market_data_interval": settings.market_data_interval,
            "market_data_period": settings.market_data_period,
            "max_data_staleness_minutes": settings.max_data_staleness_minutes,
            "regular_market_max_staleness_minutes": settings.regular_market_max_staleness_minutes,
            "min_candle_count": settings.min_candle_count,
            "min_equity_volume": settings.min_equity_volume,
            "candidate_score_threshold": settings.candidate_score_threshold,
            "scalp_candidate_score_threshold": settings.scalp_candidate_score_threshold,
            "scalp_min_abs_change_pct": settings.scalp_min_abs_change_pct,
            "scalp_min_relative_volume": settings.scalp_min_relative_volume,
            "scalp_max_contract_price": settings.scalp_max_contract_price,
            "max_scan_universe": settings.max_scan_universe,
            "max_option_spread_pct": settings.max_option_spread_pct,
            "min_option_volume": settings.min_option_volume,
            "min_option_open_interest": settings.min_option_open_interest,
            "min_option_days_to_expiration": settings.min_option_days_to_expiration,
            "max_option_days_to_expiration": settings.max_option_days_to_expiration,
            "options_data_provider": settings.options_data_provider,
            "options_realtime_required": settings.options_realtime_required,
            "max_option_quote_age_seconds": settings.max_option_quote_age_seconds,
            "has_marketdata_api_key": bool(settings.marketdata_api_key),
            "has_tradier_access_token": bool(settings.tradier_access_token),
            "has_finnhub_api_key": bool(settings.finnhub_api_key),
            "has_polygon_api_key": bool(settings.polygon_api_key),
            "has_screener_auth_token": bool(settings.screener_auth_token),
            "can_place_order_from_this_mcp": False,
        }
    )


async def version(request):
    settings: Settings = request.app.state.settings
    return JSONResponse(
        {
            "service": settings.app_name,
            "build_version": BUILD_VERSION,
            "market_data_provider": settings.market_data_provider,
            "options_data_provider": settings.options_data_provider,
            "has_finnhub_api_key": bool(settings.finnhub_api_key),
            "has_marketdata_api_key": bool(settings.marketdata_api_key),
            "has_tradier_access_token": bool(settings.tradier_access_token),
            "review_only": settings.review_only,
            "can_place_order_from_this_mcp": False,
        }
    )


async def tools(request):
    mcp = request.app.state.mcp
    listed_tools = await mcp.list_tools()
    names = [tool.name for tool in listed_tools]
    return JSONResponse({"build_version": BUILD_VERSION, "tool_count": len(names), "tools": names})
