from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return default if raw is None or raw.strip() == "" else float(raw)


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if raw is None or raw.strip() == "" else int(raw)


@dataclass(frozen=True)
class Settings:
    app_name: str = "Living Screener MCP"
    environment: str = "local"
    hosted_mode: bool = False
    screener_auth_token: str = ""
    database_path: Path = ROOT / "data" / "living_screener.sqlite3"
    review_only: bool = True
    place_orders: bool = False
    market_orders_allowed: bool = False
    manual_approval_required: bool = True
    approval_phrase: str = "APPROVED EXACT ORDER"
    max_trade_risk_pct: float = 0.10
    warn_daily_drawdown_pct: float = 0.10
    soft_stop_daily_drawdown_pct: float = 0.20
    hard_lockout_daily_drawdown_pct: float = 0.30
    max_daily_closed_losses: int = 3
    max_daily_real_cash_closed_losses: int = 3
    require_broker_review: bool = True
    pending_buy_recheck_seconds: int = 60
    max_pending_order_price_drift_pct: float = 0.003
    default_watchlist: tuple[str, ...] = ("SPY", "QQQ", "KO", "PG", "HOOD", "LULU")
    scalp_watchlist: tuple[str, ...] = (
        "SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", "AMD", "TSLA", "AMZN",
        "META", "GOOGL", "NFLX", "AVGO", "SMCI", "PLTR", "COIN", "HOOD", "SOFI",
        "RBLX", "UBER", "SHOP", "JPM", "BAC", "XOM", "CVX", "LLY", "UNH", "LULU",
        "PG", "KO",
    )
    max_scan_universe: int = 75
    market_data_provider: str = "none"
    market_data_interval: str = "5m"
    market_data_period: str = "5d"
    max_data_staleness_minutes: int = 1440
    regular_market_max_staleness_minutes: int = 15
    min_candle_count: int = 10
    min_equity_volume: int = 500_000
    candidate_score_threshold: float = 65.0
    scalp_candidate_score_threshold: float = 65.0
    scalp_min_abs_change_pct: float = 0.006
    scalp_min_relative_volume: float = 1.15
    scalp_max_contract_price: float = 1.00
    max_option_spread_pct: float = 0.18
    min_option_volume: int = 10
    min_option_open_interest: int = 50
    min_option_days_to_expiration: int = 1
    max_option_days_to_expiration: int = 45
    max_option_contracts_returned: int = 12
    options_data_provider: str = "manual"
    options_realtime_required: bool = True
    max_option_quote_age_seconds: int = 60
    marketdata_api_key: str = ""
    tradier_access_token: str = ""
    tradier_base_url: str = "https://api.tradier.com/v1"
    finnhub_api_key: str = ""
    polygon_api_key: str = ""

    def validate(self) -> None:
        if not self.review_only:
            raise ValueError("Fail closed: REVIEW_ONLY must be true.")
        if self.place_orders:
            raise ValueError("Fail closed: PLACE_ORDERS must be false.")
        if self.market_orders_allowed:
            raise ValueError("Fail closed: market orders are blocked.")
        if not self.manual_approval_required:
            raise ValueError("Fail closed: manual approval is required.")
        if self.hosted_mode and not self.screener_auth_token:
            raise ValueError("Hosted mode requires SCREENER_AUTH_TOKEN.")


def get_settings() -> Settings:
    watchlist = tuple(
        item.strip().upper()
        for item in os.getenv("DEFAULT_WATCHLIST", "SPY,QQQ,KO,PG,HOOD,LULU").split(",")
        if item.strip()
    )
    scalp_watchlist = tuple(
        item.strip().upper()
        for item in os.getenv(
            "SCALP_WATCHLIST",
            "SPY,QQQ,IWM,DIA,AAPL,MSFT,NVDA,AMD,TSLA,AMZN,META,GOOGL,NFLX,AVGO,SMCI,PLTR,COIN,HOOD,SOFI,RBLX,UBER,SHOP,JPM,BAC,XOM,CVX,LLY,UNH,LULU,PG,KO",
        ).split(",")
        if item.strip()
    )
    settings = Settings(
        environment=os.getenv("SCREENER_ENV", "local"),
        hosted_mode=_bool("HOSTED_MODE", False),
        screener_auth_token=os.getenv("SCREENER_AUTH_TOKEN", ""),
        database_path=Path(os.getenv("DATABASE_PATH", str(ROOT / "data" / "living_screener.sqlite3"))),
        review_only=_bool("REVIEW_ONLY", True),
        place_orders=_bool("PLACE_ORDERS", False),
        market_orders_allowed=_bool("ALLOW_MARKET_ORDERS", False),
        manual_approval_required=_bool("REQUIRE_MANUAL_APPROVAL", True),
        approval_phrase=os.getenv("APPROVAL_PHRASE", "APPROVED EXACT ORDER"),
        max_trade_risk_pct=_float("MAX_TRADE_RISK_PCT", 0.10),
        warn_daily_drawdown_pct=_float("WARN_DAILY_DRAWDOWN_PCT", 0.10),
        soft_stop_daily_drawdown_pct=_float("SOFT_STOP_DAILY_DRAWDOWN_PCT", 0.20),
        hard_lockout_daily_drawdown_pct=_float("HARD_LOCKOUT_DAILY_DRAWDOWN_PCT", 0.30),
        max_daily_closed_losses=_int("MAX_DAILY_CLOSED_LOSSES", 3),
        max_daily_real_cash_closed_losses=_int("MAX_DAILY_REAL_CASH_CLOSED_LOSSES", _int("MAX_DAILY_CLOSED_LOSSES", 3)),
        require_broker_review=_bool("REQUIRE_BROKER_REVIEW", True),
        pending_buy_recheck_seconds=_int("PENDING_BUY_RECHECK_SECONDS", 60),
        max_pending_order_price_drift_pct=_float("MAX_PENDING_ORDER_PRICE_DRIFT_PCT", 0.003),
        default_watchlist=watchlist,
        scalp_watchlist=scalp_watchlist,
        max_scan_universe=_int("MAX_SCAN_UNIVERSE", 75),
        market_data_provider=os.getenv("MARKET_DATA_PROVIDER", "none").strip().lower(),
        market_data_interval=os.getenv("MARKET_DATA_INTERVAL", "5m"),
        market_data_period=os.getenv("MARKET_DATA_PERIOD", "5d"),
        max_data_staleness_minutes=_int("MAX_DATA_STALENESS_MINUTES", 1440),
        regular_market_max_staleness_minutes=_int("REGULAR_MARKET_MAX_STALENESS_MINUTES", 15),
        min_candle_count=_int("MIN_CANDLE_COUNT", 10),
        min_equity_volume=_int("MIN_EQUITY_VOLUME", 500000),
        candidate_score_threshold=_float("CANDIDATE_SCORE_THRESHOLD", 65.0),
        scalp_candidate_score_threshold=_float("SCALP_CANDIDATE_SCORE_THRESHOLD", 65.0),
        scalp_min_abs_change_pct=_float("SCALP_MIN_ABS_CHANGE_PCT", 0.006),
        scalp_min_relative_volume=_float("SCALP_MIN_RELATIVE_VOLUME", 1.15),
        scalp_max_contract_price=_float("SCALP_MAX_CONTRACT_PRICE", 1.00),
        max_option_spread_pct=_float("MAX_OPTION_SPREAD_PCT", 0.18),
        min_option_volume=_int("MIN_OPTION_VOLUME", 10),
        min_option_open_interest=_int("MIN_OPTION_OPEN_INTEREST", 50),
        min_option_days_to_expiration=_int("MIN_OPTION_DAYS_TO_EXPIRATION", 1),
        max_option_days_to_expiration=_int("MAX_OPTION_DAYS_TO_EXPIRATION", 45),
        max_option_contracts_returned=_int("MAX_OPTION_CONTRACTS_RETURNED", 12),
        options_data_provider=os.getenv("OPTIONS_DATA_PROVIDER", "manual").strip().lower(),
        options_realtime_required=_bool("OPTIONS_REALTIME_REQUIRED", True),
        max_option_quote_age_seconds=_int("MAX_OPTION_QUOTE_AGE_SECONDS", 60),
        marketdata_api_key=os.getenv("MARKETDATA_API_KEY", os.getenv("MARKETDATA_TOKEN", "")),
        tradier_access_token=os.getenv("TRADIER_ACCESS_TOKEN", ""),
        tradier_base_url=os.getenv("TRADIER_BASE_URL", "https://api.tradier.com/v1").rstrip("/"),
        finnhub_api_key=os.getenv("FINNHUB_API_KEY", ""),
        polygon_api_key=os.getenv("POLYGON_API_KEY", ""),
    )
    settings.validate()
    return settings
